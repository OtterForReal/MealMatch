import json
import urllib.error
import urllib.parse
import urllib.request
from flask import Flask, render_template, request, session

app = Flask(__name__)
app.secret_key = "mealmatch_secret_key"


def safe_get(base_url, args):
    url = base_url + "?" + urllib.parse.urlencode(args)

    try:
        with urllib.request.urlopen(url) as response:
            data = response.read().decode()
    except urllib.error.HTTPError as e:
        print("Error from server. Error code:", e.code)
        return None
    except urllib.error.URLError as e:
        print("Failed to reach server. Reason:", e.reason)
        return None

    return json.loads(data)


def get_meals_by_ingredient(ingredient):
    base_url = "https://www.themealdb.com/api/json/v1/1/filter.php"
    args = {"i": ingredient}
    return safe_get(base_url, args)


def get_meal_details(meal_id):
    base_url = "https://www.themealdb.com/api/json/v1/1/lookup.php"
    args = {"i": meal_id}
    return safe_get(base_url, args)


def get_ingredient_list(meal):
    ingredients = []

    for i in range(1, 21):
        ingredient_name = meal["strIngredient" + str(i)]
        measure = meal["strMeasure" + str(i)]

        if ingredient_name is not None and ingredient_name != "":
            if measure is not None and measure != "":
                ingredient_text = measure + " " + ingredient_name
            else:
                ingredient_text = ingredient_name

            ingredients.append(ingredient_text)

    return ingredients


def get_instruction_steps(meal):
    steps = []
    instruction_text = meal["strInstructions"]

    if instruction_text is None:
        return steps

    split_steps = instruction_text.split(". ")

    for step in split_steps:
        clean_step = step.strip()

        if clean_step != "":
            if clean_step.endswith("."):
                steps.append(clean_step)
            else:
                steps.append(clean_step + ".")

    return steps


def meal_has_avoid_ingredient(meal, avoid):
    if avoid == "":
        return False

    avoid_word = avoid.lower()

    for i in range(1, 21):
        ingredient_name = meal["strIngredient" + str(i)]

        if ingredient_name is not None and ingredient_name != "":
            if avoid_word in ingredient_name.lower():
                return True

    return False


def meal_matches_cuisine(meal, cuisine):
    if cuisine == "" or cuisine == "Any":
        return True

    if meal["strArea"] is None:
        return False

    return meal["strArea"].lower() == cuisine.lower()


def meal_matches_craving(meal, craving):
    if craving == "" or craving == "Any":
        return True

    meal_name = meal["strMeal"].lower()
    category = ""

    if meal["strCategory"] is not None:
        category = meal["strCategory"].lower()

    ingredients = get_ingredient_list(meal)
    ingredient_count = len(ingredients)

    if craving == "Spicy":
        if "spicy" in meal_name or "curry" in meal_name or "chili" in meal_name or "pepper" in meal_name:
            return True
        else:
            return False

    elif craving == "Comfort food":
        if "pie" in meal_name or "stew" in meal_name or "hotpot" in meal_name or "bake" in meal_name or "roast" in meal_name:
            return True
        else:
            return False

    elif craving == "Healthy":
        if "salad" in meal_name or "grill" in meal_name or "steam" in meal_name or "vegetable" in meal_name:
            return True
        else:
            return False

    elif craving == "Quick meal":
        if ingredient_count <= 14:
            return True
        else:
            return False

    elif craving == "Savory":
        if "main course" in category or "beef" in category or "chicken" in category or "pork" in category:
            return True
        else:
            return False

    return True


def get_match_reason(meal, craving, cuisine, avoid):
    reason_parts = []

    if craving != "" and craving != "Any":
        reason_parts.append("Matches your craving for " + craving.lower())

    if cuisine != "" and cuisine != "Any":
        reason_parts.append("Cuisine: " + meal["strArea"])

    if avoid != "":
        reason_parts.append("Avoids " + avoid)

    if len(reason_parts) == 0:
        return "Fits your search"

    return " • ".join(reason_parts)


def find_allowed_meals(meal_list, avoid, cuisine, craving):
    allowed_meals = []

    for short_meal in meal_list:
        meal_id = short_meal["idMeal"]
        details = get_meal_details(meal_id)

        if details is not None and details["meals"] is not None:
            full_meal = details["meals"][0]

            if not meal_has_avoid_ingredient(full_meal, avoid):
                if meal_matches_cuisine(full_meal, cuisine):
                    if meal_matches_craving(full_meal, craving):
                        full_meal["match_reason"] = get_match_reason(full_meal, craving, cuisine, avoid)
                        allowed_meals.append(full_meal)

    return allowed_meals


@app.route("/")
def intro():
    return render_template("intro.html")


@app.route("/home")
def index():
    craving_choices = ["Any", "Comfort food", "Spicy", "Healthy", "Savory", "Quick meal"]
    cuisine_choices = ["Any", "American", "British", "Canadian", "Chinese", "Croatian", "French", "Indian", "Italian", "Japanese", "Mexican", "Thai"]

    return render_template(
        "index.html",
        craving_choices=craving_choices,
        cuisine_choices=cuisine_choices
    )


@app.route("/results", methods=["POST"])
def results():
    craving = request.form["craving"]
    cuisine = request.form["cuisine"]
    ingredient = request.form["ingredient"]
    avoid = request.form["avoid"]

    session["craving"] = craving
    session["cuisine"] = cuisine
    session["ingredient"] = ingredient
    session["avoid"] = avoid

    data = get_meals_by_ingredient(ingredient)

    if data is None or data["meals"] is None:
        return render_template(
            "results.html",
            craving=craving,
            cuisine=cuisine,
            ingredient=ingredient,
            avoid=avoid,
            meals=[],
            has_more=False,
            next_start=3
        )

    all_meals = find_allowed_meals(data["meals"], avoid, cuisine, craving)
    first_three = all_meals[0:3]
    has_more = len(all_meals) > 3

    return render_template(
        "results.html",
        craving=craving,
        cuisine=cuisine,
        ingredient=ingredient,
        avoid=avoid,
        meals=first_three,
        has_more=has_more,
        next_start=3
    )


@app.route("/more/<int:start_index>")
def more_results(start_index):
    craving = session["craving"]
    cuisine = session["cuisine"]
    ingredient = session["ingredient"]
    avoid = session["avoid"]

    data = get_meals_by_ingredient(ingredient)

    if data is None or data["meals"] is None:
        return render_template(
            "results.html",
            craving=craving,
            cuisine=cuisine,
            ingredient=ingredient,
            avoid=avoid,
            meals=[],
            has_more=False,
            next_start=start_index + 3
        )

    all_meals = find_allowed_meals(data["meals"], avoid, cuisine, craving)
    current_meals = all_meals[0:start_index + 3]
    has_more = len(all_meals) > start_index + 3

    return render_template(
        "results.html",
        craving=craving,
        cuisine=cuisine,
        ingredient=ingredient,
        avoid=avoid,
        meals=current_meals,
        has_more=has_more,
        next_start=start_index + 3
    )


@app.route("/meal/<meal_id>")
def meal_detail(meal_id):
    details = get_meal_details(meal_id)

    if details is None or details["meals"] is None:
        return "Meal not found", 404

    meal = details["meals"][0]
    ingredients = get_ingredient_list(meal)
    instruction_steps = get_instruction_steps(meal)

    return render_template(
        "meal_detail.html",
        meal=meal,
        ingredients=ingredients,
        instruction_steps=instruction_steps
    )


if __name__ == "__main__":
    app.run(debug=True)