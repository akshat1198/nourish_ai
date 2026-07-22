"""Generate the seed corpus: ingredients.json, recipes.json, substitutions.json.

Recipes are composed deterministically from dish templates x protein/veg variants.
Diet labels, allergens, and nutrition are DERIVED from canonical ingredient
properties — never hand-tagged — so labels are consistent by construction
(the validator and eval harness rely on this).

Run:  python scripts/generate_corpus.py   (from backend/)
Output is committed to backend/seed_data/ so the corpus is reviewable and stable.
"""
import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "seed_data"

# ---------------------------------------------------------------------------
# Canonical ingredients
# (name, category, aliases, allergens, vegan, vegetarian, unit, grams_per_unit,
#  kcal, protein_g, carbs_g, fat_g)  — nutrition per 100 g
# ---------------------------------------------------------------------------
F, T = False, True
INGREDIENTS = [
    # proteins
    ("chicken breast", "protein", ["chicken"], [], F, F, "g", 1, 165, 31, 0, 3.6),
    ("chicken thigh", "protein", ["chicken thighs"], [], F, F, "g", 1, 209, 26, 0, 11),
    ("ground beef", "protein", ["beef mince", "minced beef"], [], F, F, "g", 1, 250, 26, 0, 15),
    ("beef sirloin", "protein", ["steak", "beef steak"], [], F, F, "g", 1, 206, 26, 0, 11),
    ("pork loin", "protein", ["pork"], [], F, F, "g", 1, 242, 27, 0, 14),
    ("bacon", "protein", [], [], F, F, "slice", 15, 541, 37, 1.4, 42),
    ("turkey", "protein", ["ground turkey"], [], F, F, "g", 1, 189, 29, 0, 7),
    ("salmon", "protein", ["salmon fillet"], ["fish"], F, F, "g", 1, 208, 20, 0, 13),
    ("cod", "protein", ["white fish"], ["fish"], F, F, "g", 1, 82, 18, 0, 0.7),
    ("tuna", "protein", ["canned tuna"], ["fish"], F, F, "g", 1, 132, 28, 0, 1.3),
    ("shrimp", "protein", ["prawns"], ["shellfish"], F, F, "g", 1, 99, 24, 0.2, 0.3),
    ("tofu", "protein", ["bean curd"], ["soy"], T, T, "g", 1, 76, 8, 1.9, 4.8),
    ("tempeh", "protein", [], ["soy"], T, T, "g", 1, 192, 20, 7.6, 11),
    ("eggs", "protein", ["egg"], ["eggs"], F, T, "unit", 50, 155, 13, 1.1, 11),
    ("paneer", "protein", [], ["dairy"], F, T, "g", 1, 265, 18, 1.2, 21),
    ("chickpeas", "protein", ["garbanzo beans"], [], T, T, "g", 1, 164, 8.9, 27, 2.6),
    ("black beans", "protein", [], [], T, T, "g", 1, 132, 8.9, 24, 0.5),
    ("kidney beans", "protein", [], [], T, T, "g", 1, 127, 8.7, 23, 0.5),
    ("lentils", "protein", ["red lentils"], [], T, T, "g", 1, 116, 9, 20, 0.4),
    # grains & starches
    ("pasta", "grain", ["spaghetti", "penne"], ["gluten"], T, T, "g", 1, 157, 5.8, 31, 0.9),
    ("rice", "grain", ["white rice"], [], T, T, "g", 1, 130, 2.7, 28, 0.3),
    ("brown rice", "grain", [], [], T, T, "g", 1, 111, 2.6, 23, 0.9),
    ("arborio rice", "grain", ["risotto rice"], [], T, T, "g", 1, 130, 2.4, 29, 0.2),
    ("quinoa", "grain", [], [], T, T, "g", 1, 120, 4.4, 21, 1.9),
    ("rice noodles", "grain", [], [], T, T, "g", 1, 109, 0.9, 25, 0.2),
    ("egg noodles", "grain", [], ["gluten", "eggs"], F, T, "g", 1, 138, 4.5, 25, 2.1),
    ("couscous", "grain", [], ["gluten"], T, T, "g", 1, 112, 3.8, 23, 0.2),
    ("bread", "grain", ["sourdough", "buns"], ["gluten"], T, T, "slice", 40, 265, 9, 49, 3.2),
    ("tortillas", "grain", ["wraps"], ["gluten"], T, T, "unit", 45, 306, 8.2, 49, 7.7),
    ("oats", "grain", ["rolled oats"], [], T, T, "g", 1, 389, 17, 66, 7),
    ("flour", "grain", ["all-purpose flour"], ["gluten"], T, T, "g", 1, 364, 10, 76, 1),
    ("potatoes", "starch", ["potato"], [], T, T, "g", 1, 77, 2, 17, 0.1),
    ("sweet potato", "starch", ["sweet potatoes"], [], T, T, "g", 1, 86, 1.6, 20, 0.1),
    # vegetables
    ("tomato", "vegetable", ["tomatoes", "cherry tomatoes"], [], T, T, "unit", 120, 18, 0.9, 3.9, 0.2),
    ("garlic", "vegetable", ["garlic cloves"], [], T, T, "clove", 5, 149, 6.4, 33, 0.5),
    ("onion", "vegetable", ["yellow onion", "onions"], [], T, T, "unit", 110, 40, 1.1, 9.3, 0.1),
    ("red onion", "vegetable", [], [], T, T, "unit", 110, 40, 1.1, 9.3, 0.1),
    ("bell pepper", "vegetable", ["capsicum", "red pepper"], [], T, T, "unit", 120, 31, 1, 6, 0.3),
    ("zucchini", "vegetable", ["courgette"], [], T, T, "unit", 200, 17, 1.2, 3.1, 0.3),
    ("spinach", "vegetable", ["baby spinach"], [], T, T, "g", 1, 23, 2.9, 3.6, 0.4),
    ("kale", "vegetable", [], [], T, T, "g", 1, 49, 4.3, 8.8, 0.9),
    ("broccoli", "vegetable", [], [], T, T, "g", 1, 34, 2.8, 6.6, 0.4),
    ("carrot", "vegetable", ["carrots"], [], T, T, "unit", 60, 41, 0.9, 9.6, 0.2),
    ("celery", "vegetable", [], [], T, T, "stalk", 40, 16, 0.7, 3, 0.2),
    ("mushroom", "vegetable", ["mushrooms", "cremini"], [], T, T, "g", 1, 22, 3.1, 3.3, 0.3),
    ("green beans", "vegetable", [], [], T, T, "g", 1, 31, 1.8, 7, 0.2),
    ("peas", "vegetable", ["frozen peas"], [], T, T, "g", 1, 81, 5.4, 14, 0.4),
    ("corn", "vegetable", ["sweet corn"], [], T, T, "g", 1, 86, 3.3, 19, 1.4),
    ("cucumber", "vegetable", [], [], T, T, "unit", 200, 15, 0.7, 3.6, 0.1),
    ("lettuce", "vegetable", ["romaine"], [], T, T, "g", 1, 15, 1.4, 2.9, 0.2),
    ("avocado", "vegetable", [], [], T, T, "unit", 150, 160, 2, 8.5, 15),
    ("cauliflower", "vegetable", [], [], T, T, "g", 1, 25, 1.9, 5, 0.3),
    ("eggplant", "vegetable", ["aubergine"], [], T, T, "unit", 300, 25, 1, 5.9, 0.2),
    ("scallion", "vegetable", ["green onion", "spring onion"], [], T, T, "unit", 15, 32, 1.8, 7.3, 0.2),
    ("ginger", "vegetable", ["fresh ginger"], [], T, T, "g", 1, 80, 1.8, 18, 0.8),
    ("cabbage", "vegetable", [], [], T, T, "g", 1, 25, 1.3, 5.8, 0.1),
    # herbs & fruit
    ("basil", "herb", ["fresh basil"], [], T, T, "g", 1, 23, 3.2, 2.7, 0.6),
    ("cilantro", "herb", ["coriander", "fresh coriander"], [], T, T, "g", 1, 23, 2.1, 3.7, 0.5),
    ("parsley", "herb", [], [], T, T, "g", 1, 36, 3, 6.3, 0.8),
    ("lemon", "fruit", [], [], T, T, "unit", 60, 29, 1.1, 9.3, 0.3),
    ("lime", "fruit", [], [], T, T, "unit", 50, 30, 0.7, 11, 0.2),
    ("banana", "fruit", ["bananas"], [], T, T, "unit", 120, 89, 1.1, 23, 0.3),
    # dairy
    ("butter", "dairy", [], ["dairy"], F, T, "g", 1, 717, 0.9, 0.1, 81),
    ("milk", "dairy", ["whole milk"], ["dairy"], F, T, "ml", 1, 61, 3.2, 4.8, 3.3),
    ("heavy cream", "dairy", ["double cream"], ["dairy"], F, T, "ml", 1, 340, 2.1, 2.8, 36),
    ("cheddar", "dairy", ["cheddar cheese"], ["dairy"], F, T, "g", 1, 403, 25, 1.3, 33),
    ("parmesan", "dairy", ["parmesan cheese"], ["dairy"], F, T, "g", 1, 431, 38, 4.1, 29),
    ("mozzarella", "dairy", [], ["dairy"], F, T, "g", 1, 280, 28, 3.1, 17),
    ("feta", "dairy", ["feta cheese"], ["dairy"], F, T, "g", 1, 264, 14, 4.1, 21),
    ("greek yogurt", "dairy", ["yogurt"], ["dairy"], F, T, "g", 1, 59, 10, 3.6, 0.4),
    ("cream cheese", "dairy", [], ["dairy"], F, T, "g", 1, 342, 6.2, 4.1, 34),
    # pantry & sauces
    ("olive oil", "pantry", [], [], T, T, "tbsp", 14, 884, 0, 0, 100),
    ("vegetable oil", "pantry", ["canola oil"], [], T, T, "tbsp", 14, 884, 0, 0, 100),
    ("sesame oil", "pantry", [], ["sesame"], T, T, "tbsp", 14, 884, 0, 0, 100),
    ("soy sauce", "sauce", [], ["soy", "gluten"], T, T, "tbsp", 16, 53, 8.1, 4.9, 0.6),
    ("coconut milk", "pantry", [], [], T, T, "ml", 1, 230, 2.3, 5.5, 24),
    ("curry paste", "sauce", ["thai curry paste"], [], T, T, "tbsp", 20, 120, 2, 12, 7),
    ("curry powder", "spice", [], [], T, T, "tsp", 3, 325, 14, 56, 14),
    ("cumin", "spice", [], [], T, T, "tsp", 3, 375, 18, 44, 22),
    ("paprika", "spice", ["smoked paprika"], [], T, T, "tsp", 3, 282, 14, 54, 13),
    ("chili flakes", "spice", ["red pepper flakes"], [], T, T, "tsp", 2, 318, 12, 57, 17),
    ("oregano", "spice", ["dried oregano"], [], T, T, "tsp", 2, 265, 9, 69, 4.3),
    ("thyme", "spice", [], [], T, T, "tsp", 2, 276, 9.1, 64, 7.4),
    ("black pepper", "spice", [], [], T, T, "tsp", 3, 251, 10, 64, 3.3),
    ("salt", "spice", [], [], T, T, "tsp", 6, 0, 0, 0, 0),
    ("vinegar", "pantry", ["rice vinegar"], [], T, T, "tbsp", 15, 18, 0, 0.9, 0),
    ("honey", "pantry", [], [], F, T, "tbsp", 21, 304, 0.3, 82, 0),
    ("maple syrup", "pantry", [], [], T, T, "tbsp", 20, 260, 0, 67, 0),
    ("sugar", "pantry", [], [], T, T, "tbsp", 12, 387, 0, 100, 0),
    ("tomato paste", "pantry", [], [], T, T, "tbsp", 16, 82, 4.3, 19, 0.5),
    ("canned tomatoes", "pantry", ["crushed tomatoes", "diced tomatoes"], [], T, T, "g", 1, 18, 0.9, 3.9, 0.2),
    ("vegetable broth", "pantry", ["vegetable stock"], [], T, T, "ml", 1, 5, 0.2, 1, 0),
    ("chicken broth", "pantry", ["chicken stock"], [], F, F, "ml", 1, 7, 0.6, 0.9, 0.2),
    ("peanut butter", "pantry", [], ["nuts"], T, T, "tbsp", 16, 588, 25, 20, 50),
    ("peanuts", "pantry", [], ["nuts"], T, T, "g", 1, 567, 26, 16, 49),
    ("cashews", "pantry", [], ["nuts"], T, T, "g", 1, 553, 18, 30, 44),
    ("almonds", "pantry", [], ["nuts"], T, T, "g", 1, 579, 21, 22, 50),
    ("walnuts", "pantry", [], ["nuts"], T, T, "g", 1, 654, 15, 14, 65),
    ("tahini", "pantry", [], ["sesame"], T, T, "tbsp", 15, 595, 17, 21, 54),
]

ING = {row[0]: row for row in INGREDIENTS}
UNIT_GRAMS = {"g": 1, "ml": 1}  # other units use grams_per_unit from the row


def grams(name, qty, unit):
    row = ING[name]
    if unit in UNIT_GRAMS:
        return qty
    return qty * row[7]


# ---------------------------------------------------------------------------
# Dish templates
# item tuple: (name, qty, unit, essential)
# protein slot tuple: (name, qty_grams, title_word or None)
# ---------------------------------------------------------------------------
def tw(name):
    """Title word for an ingredient."""
    return name.title()


TEMPLATES = [
    dict(
        title="{p} & {v} Stir-Fry",
        cuisine="asian", method="stir-fry", time=20, servings=2,
        desc="A fast weeknight stir-fry: {pl} and crisp {vl} tossed in a garlicky soy-ginger glaze over steamed rice.",
        base=[("rice", 150, "g", True), ("soy sauce", 2, "tbsp", True), ("garlic", 2, "clove", True),
              ("ginger", 10, "g", False), ("vegetable oil", 1, "tbsp", False), ("scallion", 2, "unit", False)],
        proteins=[("chicken breast", 300), ("beef sirloin", 300), ("shrimp", 250),
                  ("tofu", 300), ("tempeh", 250), ("pork loin", 300)],
        veg_pool=["broccoli", "bell pepper", "carrot", "zucchini", "mushroom", "green beans"],
        veg_qty=(150, "g"), veg_variants=3,
        steps=["Cook the rice according to package directions.",
               "Sear the {pl} in a hot wok with oil until just cooked; set aside.",
               "Stir-fry the {vl} with garlic and ginger for 3-4 minutes.",
               "Return the {pl}, add soy sauce, toss for 1 minute and serve over rice topped with scallions."],
    ),
    dict(
        title="{p} & {v} Coconut Curry",
        cuisine="thai", method="simmer", time=35, servings=4,
        desc="Fragrant coconut curry with {pl} and {vl}, simmered with curry paste and finished with lime.",
        base=[("rice", 200, "g", True), ("coconut milk", 400, "ml", True), ("curry paste", 2, "tbsp", True),
              ("onion", 1, "unit", True), ("garlic", 2, "clove", False), ("lime", 1, "unit", False),
              ("cilantro", 10, "g", False), ("vegetable oil", 1, "tbsp", False)],
        proteins=[("chicken thigh", 400), ("shrimp", 300), ("chickpeas", 300),
                  ("tofu", 350), ("cod", 350), ("lentils", 250), ("paneer", 300)],
        veg_pool=["spinach", "green beans", "sweet potato", "cauliflower", "bell pepper", "eggplant"],
        veg_qty=(200, "g"), veg_variants=3,
        steps=["Sauté onion and garlic in oil until soft, then bloom the curry paste for 1 minute.",
               "Add coconut milk and bring to a gentle simmer.",
               "Add the {pl} and {vl}; simmer until cooked through and tender.",
               "Serve over rice with lime wedges and cilantro."],
    ),
    dict(
        title="Creamy {p} Pasta",
        cuisine="italian", method="stovetop", time=25, servings=2,
        desc="Silky cream and parmesan sauce coating al dente pasta with {pl}.",
        base=[("pasta", 200, "g", True), ("heavy cream", 150, "ml", True), ("parmesan", 40, "g", True),
              ("garlic", 2, "clove", True), ("butter", 15, "g", False), ("black pepper", 1, "tsp", False),
              ("parsley", 5, "g", False)],
        proteins=[("chicken breast", 250), ("shrimp", 200), ("mushroom", 250),
                  ("bacon", 4, "slice"), ("salmon", 250), ("turkey", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Cook the pasta in salted water until al dente; reserve a cup of pasta water.",
               "Cook the {pl} in butter with garlic until done.",
               "Add cream, simmer 2 minutes, then melt in the parmesan.",
               "Toss with the pasta, loosening with pasta water; finish with pepper and parsley."],
    ),
    dict(
        title="{p} Tacos",
        cuisine="mexican", method="stovetop", time=25, servings=3,
        desc="Street-style tacos: seasoned {pl} with charred onion, fresh cilantro and a squeeze of lime.",
        base=[("tortillas", 6, "unit", True), ("onion", 1, "unit", True), ("lime", 1, "unit", True),
              ("cilantro", 10, "g", False), ("cumin", 2, "tsp", True), ("paprika", 1, "tsp", False),
              ("vegetable oil", 1, "tbsp", False), ("lettuce", 50, "g", False)],
        proteins=[("ground beef", 350), ("chicken thigh", 350), ("black beans", 300),
                  ("cod", 300), ("shrimp", 250), ("tofu", 300), ("turkey", 350)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Season the {pl} with cumin and paprika.",
               "Cook in a hot skillet with oil until browned and cooked through.",
               "Warm the tortillas; char the onion slices.",
               "Assemble tacos with lettuce, cilantro and plenty of lime."],
    ),
    dict(
        title="{p} Quinoa Bowl",
        cuisine="fusion", method="assembled", time=30, servings=2,
        desc="A hearty grain bowl: fluffy quinoa, {pl}, creamy avocado and greens with a lemon dressing.",
        base=[("quinoa", 150, "g", True), ("avocado", 1, "unit", True), ("spinach", 80, "g", True),
              ("lemon", 1, "unit", False), ("olive oil", 2, "tbsp", False), ("cucumber", 1, "unit", False)],
        proteins=[("chickpeas", 250), ("salmon", 250), ("chicken breast", 250),
                  ("tofu", 250), ("black beans", 250), ("tempeh", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Cook the quinoa and let it steam dry.",
               "Prepare the {pl} — roast or pan-sear until golden.",
               "Whisk lemon juice with olive oil for the dressing.",
               "Assemble bowls with quinoa, greens, {pl}, avocado and cucumber; dress generously."],
    ),
    dict(
        title="{p} Vegetable Soup",
        cuisine="american", method="simmer", time=40, servings=4,
        desc="A comforting pot of soup: {pl} with carrot, celery and onion in a savory broth.",
        base=[("vegetable broth", 1000, "ml", True), ("carrot", 2, "unit", True), ("celery", 2, "stalk", True),
              ("onion", 1, "unit", True), ("garlic", 2, "clove", False), ("thyme", 1, "tsp", False),
              ("olive oil", 1, "tbsp", False)],
        proteins=[("chicken breast", 300), ("lentils", 200), ("kidney beans", 300), ("turkey", 300), ("chickpeas", 300)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Sweat onion, carrot and celery in olive oil until soft.",
               "Add garlic and thyme; cook 1 minute.",
               "Add broth and the {pl}; simmer until everything is tender.",
               "Season and serve hot."],
    ),
    dict(
        title="{p} Salad",
        cuisine="mediterranean", method="assembled", time=15, servings=2,
        desc="A bright, crunchy salad with {pl}, tomato and cucumber in a lemon-olive oil dressing.",
        base=[("lettuce", 100, "g", True), ("tomato", 2, "unit", True), ("cucumber", 1, "unit", True),
              ("red onion", 1, "unit", False), ("olive oil", 2, "tbsp", True), ("lemon", 1, "unit", True)],
        proteins=[("chicken breast", 250), ("tuna", 200), ("chickpeas", 250),
                  ("feta", 120), ("shrimp", 200), ("salmon", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Chop the lettuce, tomato, cucumber and red onion.",
               "Prepare the {pl} (grill, drain or crumble as appropriate).",
               "Whisk lemon juice and olive oil; season well.",
               "Toss everything together and serve immediately."],
    ),
    dict(
        title="{p} Fried Rice",
        cuisine="chinese", method="stir-fry", time=20, servings=2,
        desc="Takeout-style fried rice with {pl}, peas, egg and scallions.",
        base=[("rice", 300, "g", True), ("eggs", 2, "unit", True), ("peas", 100, "g", True),
              ("scallion", 3, "unit", True), ("soy sauce", 2, "tbsp", True), ("sesame oil", 1, "tbsp", False),
              ("garlic", 2, "clove", False), ("vegetable oil", 1, "tbsp", False)],
        proteins=[("chicken breast", 250), ("shrimp", 200), ("pork loin", 250), ("tofu", 250), ("beef sirloin", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Cook the {pl} in a hot wok; set aside.",
               "Scramble the eggs, then add cold cooked rice and break it up.",
               "Add peas, garlic and the {pl}; toss over high heat.",
               "Season with soy sauce and sesame oil; finish with scallions."],
    ),
    dict(
        title="Sheet-Pan {p} with {v}",
        cuisine="american", method="roast", time=45, servings=4,
        desc="An easy sheet-pan dinner: {pl} roasted alongside potatoes and {vl} with paprika and thyme.",
        base=[("potatoes", 500, "g", True), ("olive oil", 2, "tbsp", True), ("paprika", 2, "tsp", True),
              ("thyme", 1, "tsp", False), ("garlic", 3, "clove", False), ("lemon", 1, "unit", False)],
        proteins=[("chicken thigh", 500), ("salmon", 400), ("cod", 400),
                  ("pork loin", 450), ("tofu", 400)],
        veg_pool=["broccoli", "carrot", "zucchini", "cauliflower", "green beans"],
        veg_qty=(250, "g"), veg_variants=2,
        steps=["Heat the oven to 220°C / 425°F.",
               "Toss potatoes and {vl} with oil, paprika and thyme on a sheet pan.",
               "Nestle in the {pl}; roast until cooked through and the potatoes are crisp.",
               "Finish with lemon and a scatter of garlic in the last 10 minutes."],
    ),
    dict(
        title="{p} Chili",
        cuisine="tex-mex", method="simmer", time=50, servings=4,
        desc="A deep, smoky chili built on {pl}, kidney beans and tomatoes.",
        base=[("kidney beans", 400, "g", True), ("canned tomatoes", 400, "g", True), ("onion", 1, "unit", True),
              ("garlic", 3, "clove", True), ("cumin", 2, "tsp", True), ("paprika", 2, "tsp", True),
              ("chili flakes", 1, "tsp", False), ("tomato paste", 2, "tbsp", False), ("olive oil", 1, "tbsp", False)],
        proteins=[("ground beef", 400), ("turkey", 400), ("black beans", 300), ("lentils", 300)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Brown the {pl} with onion and garlic in olive oil.",
               "Stir in spices and tomato paste; cook until fragrant.",
               "Add tomatoes and beans; simmer low for 30 minutes.",
               "Season and serve with your favorite toppings."],
    ),
    dict(
        title="{p} Risotto",
        cuisine="italian", method="stovetop", time=40, servings=2,
        desc="Slow-stirred arborio risotto with {pl}, parmesan and butter.",
        base=[("arborio rice", 180, "g", True), ("vegetable broth", 800, "ml", True), ("parmesan", 40, "g", True),
              ("butter", 20, "g", True), ("onion", 1, "unit", True), ("garlic", 2, "clove", False)],
        proteins=[("mushroom", 250), ("shrimp", 200), ("chicken breast", 250), ("salmon", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Soften onion and garlic in half the butter.",
               "Toast the rice, then add warm broth a ladle at a time, stirring.",
               "Fold in the {pl} for the final 8-10 minutes of cooking.",
               "Finish off the heat with parmesan and the remaining butter."],
    ),
    dict(
        title="{p} Noodle Soup",
        cuisine="asian", method="simmer", time=30, servings=2,
        desc="A restorative noodle soup: {pl}, rice noodles and greens in a ginger-garlic broth.",
        base=[("rice noodles", 150, "g", True), ("chicken broth", 1000, "ml", True), ("ginger", 15, "g", True),
              ("garlic", 2, "clove", True), ("scallion", 2, "unit", False), ("soy sauce", 1, "tbsp", False),
              ("spinach", 80, "g", False)],
        proteins=[("chicken breast", 250), ("shrimp", 200), ("tofu", 250), ("beef sirloin", 250), ("turkey", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Simmer the broth with ginger and garlic for 10 minutes.",
               "Add the {pl} and cook through.",
               "Add noodles and spinach; cook until just tender.",
               "Season with soy sauce and top with scallions."],
    ),
    dict(
        title="{p} Pad Thai",
        cuisine="thai", method="stir-fry", time=25, servings=2,
        desc="Rice noodles tossed with {pl}, egg, peanuts and lime.",
        base=[("rice noodles", 200, "g", True), ("eggs", 2, "unit", True), ("peanuts", 40, "g", True),
              ("lime", 1, "unit", True), ("scallion", 3, "unit", False), ("garlic", 2, "clove", False),
              ("soy sauce", 2, "tbsp", True), ("sugar", 1, "tbsp", False), ("vegetable oil", 1, "tbsp", False)],
        proteins=[("shrimp", 250), ("chicken breast", 250), ("tofu", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Soak the rice noodles until pliable.",
               "Stir-fry the {pl} with garlic; push aside and scramble the eggs.",
               "Add noodles and sauce (soy, sugar, lime); toss over high heat.",
               "Serve topped with crushed peanuts, scallions and extra lime."],
    ),
    dict(
        title="{p} Burgers",
        cuisine="american", method="grill", time=30, servings=4,
        desc="Juicy {pl} burgers with lettuce, tomato and red onion on toasted buns.",
        base=[("bread", 4, "slice", True), ("lettuce", 40, "g", True), ("tomato", 1, "unit", True),
              ("red onion", 1, "unit", False), ("eggs", 1, "unit", False), ("olive oil", 1, "tbsp", False),
              ("black pepper", 1, "tsp", False)],
        proteins=[("ground beef", 500), ("turkey", 500), ("black beans", 400), ("chickpeas", 400), ("salmon", 400)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Form the {pl} into four patties (bind with egg if using beans).",
               "Grill or pan-sear until cooked through with a good crust.",
               "Toast the buns.",
               "Stack with lettuce, tomato and red onion."],
    ),
    dict(
        title="Grilled {p} Skewers",
        cuisine="mediterranean", method="grill", time=35, servings=3,
        desc="Char-grilled skewers of {pl}, bell pepper and red onion with lemon and oregano.",
        base=[("bell pepper", 2, "unit", True), ("red onion", 1, "unit", True), ("olive oil", 2, "tbsp", True),
              ("lemon", 1, "unit", True), ("oregano", 2, "tsp", True), ("garlic", 2, "clove", False)],
        proteins=[("chicken breast", 400), ("beef sirloin", 400), ("shrimp", 300), ("paneer", 300), ("tofu", 300)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Marinate the {pl} in olive oil, lemon, garlic and oregano.",
               "Thread onto skewers with bell pepper and red onion.",
               "Grill over high heat, turning, until charred and cooked through.",
               "Rest briefly and serve with extra lemon."],
    ),
    dict(
        title="Stuffed Peppers with {p}",
        cuisine="american", method="bake", time=50, servings=4,
        desc="Bell peppers baked until tender, stuffed with {pl}, rice and melted cheddar.",
        base=[("bell pepper", 4, "unit", True), ("rice", 150, "g", True), ("cheddar", 80, "g", True),
              ("onion", 1, "unit", True), ("garlic", 2, "clove", False), ("canned tomatoes", 200, "g", True),
              ("cumin", 1, "tsp", False), ("olive oil", 1, "tbsp", False)],
        proteins=[("ground beef", 350), ("turkey", 350), ("black beans", 300), ("lentils", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Halve and seed the peppers; roast 10 minutes.",
               "Cook the {pl} with onion, garlic, cumin and tomatoes; fold in cooked rice.",
               "Fill the peppers, top with cheddar.",
               "Bake until bubbling and the peppers are tender."],
    ),
    dict(
        title="{p} Pilaf",
        cuisine="middle-eastern", method="stovetop", time=35, servings=3,
        desc="One-pot spiced rice pilaf with {pl}, sweet carrots and toasted almonds.",
        base=[("rice", 200, "g", True), ("carrot", 2, "unit", True), ("onion", 1, "unit", True),
              ("almonds", 30, "g", False), ("cumin", 1, "tsp", True), ("vegetable broth", 450, "ml", True),
              ("olive oil", 2, "tbsp", False), ("parsley", 5, "g", False)],
        proteins=[("chickpeas", 250), ("chicken thigh", 350), ("turkey", 300), ("lentils", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Soften onion and carrot in oil; add cumin and the {pl}.",
               "Stir in the rice, then add broth and cover.",
               "Cook low until the rice is tender and liquid absorbed.",
               "Fluff and top with toasted almonds and parsley."],
    ),
    dict(
        title="{p} Wraps",
        cuisine="fusion", method="assembled", time=15, servings=2,
        desc="Quick lunch wraps: {pl} with crunchy vegetables and a yogurt-lemon spread.",
        base=[("tortillas", 2, "unit", True), ("greek yogurt", 80, "g", True), ("lettuce", 50, "g", True),
              ("cucumber", 1, "unit", True), ("tomato", 1, "unit", False), ("lemon", 1, "unit", False)],
        proteins=[("chicken breast", 200), ("tuna", 150), ("chickpeas", 200), ("turkey", 200), ("shrimp", 200)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Mix the yogurt with lemon juice and season — this is the spread.",
               "Prepare the {pl} (grill, drain or mash lightly).",
               "Layer the spread, lettuce, cucumber, tomato and {pl} on the tortillas.",
               "Roll tightly, halve, and serve."],
    ),
    dict(
        title="Baked {p} Pasta",
        cuisine="italian", method="bake", time=45, servings=4,
        desc="Bubbling baked pasta with {pl}, tomato sauce and molten mozzarella.",
        base=[("pasta", 300, "g", True), ("canned tomatoes", 400, "g", True), ("mozzarella", 150, "g", True),
              ("onion", 1, "unit", True), ("garlic", 3, "clove", True), ("oregano", 2, "tsp", False),
              ("olive oil", 2, "tbsp", False), ("parmesan", 30, "g", False)],
        proteins=[("ground beef", 350), ("chicken breast", 300), ("mushroom", 300), ("turkey", 300)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Parboil the pasta two minutes shy of al dente.",
               "Make the sauce: cook the {pl} with onion, garlic, oregano and tomatoes.",
               "Combine pasta and sauce; top with mozzarella and parmesan.",
               "Bake at 200°C / 400°F until golden and bubbling."],
    ),
    dict(
        title="Teriyaki {p} Rice Bowl",
        cuisine="japanese", method="stovetop", time=25, servings=2,
        desc="A glossy sweet-savory teriyaki glaze over seared {pl}, steamed rice and broccoli.",
        base=[("rice", 200, "g", True), ("broccoli", 200, "g", True), ("soy sauce", 3, "tbsp", True),
              ("honey", 2, "tbsp", True), ("ginger", 10, "g", True), ("garlic", 2, "clove", False),
              ("sesame oil", 1, "tbsp", False), ("scallion", 2, "unit", False)],
        proteins=[("chicken thigh", 350), ("salmon", 300), ("tofu", 300), ("tempeh", 250), ("shrimp", 250)],
        veg_pool=[], veg_qty=None, veg_variants=1,
        steps=["Steam the rice and the broccoli.",
               "Sear the {pl} until golden.",
               "Add soy, honey, ginger and garlic; reduce to a glaze.",
               "Serve over rice with broccoli, sesame oil and scallions."],
    ),
]

# Fixed, hand-specified recipes (anchors + breakfast/classics)
FIXED = [
    dict(
        title="Tomato Garlic Pasta",
        cuisine="italian", method="stovetop", time=25, servings=2,
        desc="The pantry classic: al dente spaghetti in a garlicky fresh tomato sauce with basil.",
        items=[("pasta", 200, "g", True), ("tomato", 4, "unit", True), ("garlic", 4, "clove", True),
               ("olive oil", 3, "tbsp", True), ("basil", 10, "g", False), ("chili flakes", 1, "tsp", False),
               ("parmesan", 30, "g", False)],
        steps=["Cook the pasta in well-salted water until al dente.",
               "Slowly sizzle sliced garlic in olive oil; add chopped tomatoes and collapse into a sauce.",
               "Toss the pasta through the sauce with a splash of pasta water.",
               "Finish with torn basil, chili flakes and parmesan."],
    ),
    dict(
        title="Shakshuka",
        cuisine="middle-eastern", method="stovetop", time=30, servings=2,
        desc="Eggs poached in a spiced pepper-tomato sauce — brunch in a skillet.",
        items=[("eggs", 4, "unit", True), ("canned tomatoes", 400, "g", True), ("bell pepper", 1, "unit", True),
               ("onion", 1, "unit", True), ("garlic", 3, "clove", True), ("cumin", 2, "tsp", True),
               ("paprika", 1, "tsp", True), ("olive oil", 2, "tbsp", False), ("parsley", 5, "g", False)],
        steps=["Soften onion and bell pepper in olive oil; add garlic and spices.",
               "Add tomatoes and simmer into a thick sauce.",
               "Make wells and crack in the eggs; cover and poach until just set.",
               "Scatter with parsley and serve from the pan."],
    ),
    dict(
        title="Caprese Salad",
        cuisine="italian", method="assembled", time=10, servings=2,
        desc="Ripe tomatoes, fresh mozzarella and basil with good olive oil.",
        items=[("tomato", 3, "unit", True), ("mozzarella", 150, "g", True), ("basil", 15, "g", True),
               ("olive oil", 2, "tbsp", True), ("black pepper", 1, "tsp", False), ("salt", 1, "tsp", False)],
        steps=["Slice the tomatoes and mozzarella.",
               "Shingle on a platter with basil leaves between.",
               "Season and finish with olive oil."],
    ),
    dict(
        title="Greek Salad",
        cuisine="mediterranean", method="assembled", time=15, servings=2,
        desc="Chunky cucumber, tomato and red onion with feta, oregano and olive oil.",
        items=[("cucumber", 1, "unit", True), ("tomato", 3, "unit", True), ("red onion", 1, "unit", True),
               ("feta", 120, "g", True), ("olive oil", 3, "tbsp", True), ("oregano", 1, "tsp", True),
               ("bell pepper", 1, "unit", False)],
        steps=["Cut the vegetables into chunky pieces.",
               "Combine with olive oil and oregano.",
               "Top with a slab of feta and more oregano."],
    ),
    dict(
        title="Minestrone",
        cuisine="italian", method="simmer", time=45, servings=4,
        desc="The everything-vegetable soup: beans, pasta and greens in a tomato broth.",
        items=[("vegetable broth", 1200, "ml", True), ("kidney beans", 250, "g", True), ("pasta", 100, "g", True),
               ("carrot", 2, "unit", True), ("celery", 2, "stalk", True), ("onion", 1, "unit", True),
               ("canned tomatoes", 200, "g", True), ("garlic", 2, "clove", False), ("kale", 80, "g", False),
               ("olive oil", 2, "tbsp", False), ("parmesan", 20, "g", False)],
        steps=["Sweat onion, carrot and celery in olive oil.",
               "Add garlic, tomatoes and broth; simmer 15 minutes.",
               "Add beans and pasta; cook until the pasta is tender.",
               "Stir through kale at the end; serve with parmesan."],
    ),
    dict(
        title="Mushroom & Spinach Frittata",
        cuisine="italian", method="bake", time=30, servings=3,
        desc="A fluffy open-faced omelette loaded with mushrooms, spinach and cheddar.",
        items=[("eggs", 6, "unit", True), ("mushroom", 200, "g", True), ("spinach", 80, "g", True),
               ("cheddar", 60, "g", True), ("onion", 1, "unit", False), ("olive oil", 1, "tbsp", False),
               ("black pepper", 1, "tsp", False)],
        steps=["Sauté mushrooms and onion until golden; wilt in the spinach.",
               "Pour over beaten eggs; scatter with cheddar.",
               "Cook gently, then finish under the broiler until puffed."],
    ),
    dict(
        title="French Cheese Omelette",
        cuisine="french", method="stovetop", time=10, servings=1,
        desc="Three eggs, butter, cheese — rolled soft and served immediately.",
        items=[("eggs", 3, "unit", True), ("butter", 20, "g", True), ("cheddar", 40, "g", True),
               ("black pepper", 1, "tsp", False), ("parsley", 3, "g", False)],
        steps=["Beat the eggs well; melt butter in a nonstick pan.",
               "Cook the eggs over medium heat, stirring, until softly set.",
               "Add cheese, roll the omelette onto a plate, and serve."],
    ),
    dict(
        title="Avocado Toast with Egg",
        cuisine="american", method="assembled", time=10, servings=1,
        desc="Smashed avocado on toasted sourdough with a soft-fried egg and chili flakes.",
        items=[("bread", 2, "slice", True), ("avocado", 1, "unit", True), ("eggs", 1, "unit", True),
               ("lemon", 1, "unit", False), ("chili flakes", 1, "tsp", False), ("olive oil", 1, "tbsp", False)],
        steps=["Toast the bread.",
               "Smash the avocado with lemon and salt; spread thickly.",
               "Top with a fried egg, chili flakes and a thread of olive oil."],
    ),
    dict(
        title="Banana Oat Pancakes",
        cuisine="american", method="stovetop", time=20, servings=2,
        desc="Naturally sweet blender pancakes from oats, banana and eggs.",
        items=[("oats", 120, "g", True), ("banana", 2, "unit", True), ("eggs", 2, "unit", True),
               ("milk", 100, "ml", True), ("maple syrup", 2, "tbsp", False), ("butter", 15, "g", False)],
        steps=["Blitz oats, banana, eggs and milk into a batter.",
               "Cook small pancakes in butter until bubbles form; flip.",
               "Stack and drench in maple syrup."],
    ),
    dict(
        title="Peanut Noodles",
        cuisine="asian", method="stovetop", time=20, servings=2,
        desc="Chewy noodles in a savory peanut-soy sauce with cucumber and scallions.",
        items=[("rice noodles", 200, "g", True), ("peanut butter", 3, "tbsp", True), ("soy sauce", 2, "tbsp", True),
               ("garlic", 2, "clove", True), ("cucumber", 1, "unit", False), ("scallion", 2, "unit", False),
               ("lime", 1, "unit", False), ("chili flakes", 1, "tsp", False)],
        steps=["Cook the noodles and rinse cool.",
               "Whisk peanut butter, soy, garlic, lime and a splash of water into a sauce.",
               "Toss the noodles in the sauce.",
               "Top with cucumber matchsticks, scallions and chili flakes."],
    ),
    dict(
        title="Lentil Dal",
        cuisine="indian", method="simmer", time=40, servings=4,
        desc="Creamy spiced red lentils tempered with garlic and cumin.",
        items=[("lentils", 300, "g", True), ("onion", 1, "unit", True), ("garlic", 4, "clove", True),
               ("ginger", 15, "g", True), ("cumin", 2, "tsp", True), ("curry powder", 2, "tsp", True),
               ("canned tomatoes", 200, "g", False), ("vegetable oil", 2, "tbsp", False),
               ("cilantro", 10, "g", False), ("rice", 200, "g", False)],
        steps=["Simmer lentils until soft and collapsing.",
               "Fry onion, garlic, ginger and spices; add tomatoes.",
               "Fold the temper through the lentils; loosen to taste.",
               "Serve over rice with cilantro."],
    ),
    dict(
        title="Paneer Tikka Masala",
        cuisine="indian", method="simmer", time=40, servings=3,
        desc="Charred paneer in a rich, creamy spiced tomato sauce.",
        items=[("paneer", 300, "g", True), ("canned tomatoes", 400, "g", True), ("heavy cream", 100, "ml", True),
               ("onion", 1, "unit", True), ("garlic", 3, "clove", True), ("ginger", 15, "g", True),
               ("curry powder", 2, "tsp", True), ("cumin", 1, "tsp", False), ("butter", 20, "g", False),
               ("rice", 200, "g", False), ("cilantro", 10, "g", False)],
        steps=["Sear the paneer cubes until golden; set aside.",
               "Cook onion, garlic, ginger and spices in butter; add tomatoes and simmer.",
               "Blend smooth, stir in cream, and return the paneer.",
               "Serve with rice and cilantro."],
    ),
]

# ---------------------------------------------------------------------------
# Substitutions: (ingredient, substitute, ratio, confidence, diet_ok)
# ---------------------------------------------------------------------------
SUBSTITUTIONS = [
    ("butter", "olive oil", "1:0.75", 0.9, ["vegan", "dairy_free"]),
    ("heavy cream", "coconut milk", "1:1", 0.85, ["vegan", "dairy_free"]),
    ("milk", "coconut milk", "1:1", 0.85, ["vegan", "dairy_free"]),
    ("greek yogurt", "coconut milk", "1:0.75", 0.6, ["vegan", "dairy_free"]),
    ("paneer", "tofu", "1:1", 0.85, ["vegan", "dairy_free"]),
    ("cheddar", "mozzarella", "1:1", 0.8, []),
    ("mozzarella", "cheddar", "1:1", 0.75, []),
    ("parmesan", "cheddar", "1:0.75", 0.6, []),
    ("cream cheese", "greek yogurt", "1:1", 0.65, []),
    ("chicken breast", "tofu", "1:1", 0.8, ["vegan", "vegetarian"]),
    ("chicken breast", "chickpeas", "1:0.8", 0.7, ["vegan", "vegetarian"]),
    ("chicken thigh", "tofu", "1:1", 0.75, ["vegan", "vegetarian"]),
    ("ground beef", "lentils", "1:0.75", 0.8, ["vegan", "vegetarian"]),
    ("ground beef", "black beans", "1:0.8", 0.75, ["vegan", "vegetarian"]),
    ("beef sirloin", "tempeh", "1:0.8", 0.7, ["vegan", "vegetarian"]),
    ("pork loin", "chicken breast", "1:1", 0.8, []),
    ("turkey", "chicken breast", "1:1", 0.85, []),
    ("shrimp", "tofu", "1:1", 0.65, ["vegan", "vegetarian", "shellfish_free"]),
    ("salmon", "tofu", "1:1", 0.6, ["vegan", "vegetarian", "fish_free"]),
    ("cod", "tofu", "1:1", 0.6, ["vegan", "vegetarian", "fish_free"]),
    ("tuna", "chickpeas", "1:1", 0.7, ["vegan", "vegetarian", "fish_free"]),
    ("eggs", "tofu", "1:0.6", 0.55, ["vegan", "egg_free"]),
    ("pasta", "rice noodles", "1:1", 0.8, ["gluten_free"]),
    ("pasta", "quinoa", "1:0.7", 0.55, ["gluten_free"]),
    ("egg noodles", "rice noodles", "1:1", 0.85, ["gluten_free", "egg_free"]),
    ("couscous", "quinoa", "1:1", 0.85, ["gluten_free"]),
    ("rice", "quinoa", "1:1", 0.8, []),
    ("rice", "brown rice", "1:1", 0.9, []),
    ("quinoa", "rice", "1:1", 0.8, []),
    ("potatoes", "sweet potato", "1:1", 0.85, []),
    ("spinach", "kale", "1:1", 0.85, []),
    ("kale", "spinach", "1:1", 0.85, []),
    ("broccoli", "cauliflower", "1:1", 0.85, []),
    ("cauliflower", "broccoli", "1:1", 0.85, []),
    ("zucchini", "eggplant", "1:1", 0.75, []),
    ("mushroom", "eggplant", "1:1", 0.6, []),
    ("cilantro", "parsley", "1:1", 0.7, []),
    ("basil", "parsley", "1:1", 0.55, []),
    ("lime", "lemon", "1:1", 0.85, []),
    ("lemon", "lime", "1:1", 0.85, []),
    ("scallion", "onion", "1:0.5", 0.6, []),
    ("onion", "red onion", "1:1", 0.9, []),
    ("honey", "maple syrup", "1:1", 0.9, ["vegan"]),
    ("sugar", "maple syrup", "1:0.75", 0.7, []),
    ("peanut butter", "tahini", "1:1", 0.75, ["nut_free"]),
    ("peanuts", "cashews", "1:1", 0.85, []),
    ("cashews", "almonds", "1:1", 0.8, []),
    ("walnuts", "almonds", "1:1", 0.8, []),
    ("chicken broth", "vegetable broth", "1:1", 0.9, ["vegan", "vegetarian"]),
    ("vegetable oil", "olive oil", "1:1", 0.9, []),
    ("sesame oil", "olive oil", "1:0.75", 0.5, ["sesame_free"]),
]

MEAT = {"chicken breast", "chicken thigh", "ground beef", "beef sirloin", "pork loin",
        "bacon", "turkey", "salmon", "cod", "tuna", "shrimp", "chicken broth"}


def derive(items):
    """Derive allergens, diet labels and per-serving-independent nutrition totals."""
    allergens, vegan, vegetarian = set(), True, True
    total = dict(calories=0.0, protein_g=0.0, carbs_g=0.0, fat_g=0.0)
    for name, qty, unit, _essential in items:
        row = ING[name]
        allergens.update(row[3])
        vegan &= row[4]
        vegetarian &= row[5]
        g = grams(name, qty, unit)
        total["calories"] += g * row[8] / 100
        total["protein_g"] += g * row[9] / 100
        total["carbs_g"] += g * row[10] / 100
        total["fat_g"] += g * row[11] / 100
    labels = []
    if vegan:
        labels.append("vegan")
    if vegetarian:
        labels.append("vegetarian")
    if not any(ING[n][0] in MEAT and "fish" not in ING[n][3] and "shellfish" not in ING[n][3]
               for n, *_ in items) and not vegetarian:
        # contains fish/shellfish but no land meat
        if all(("fish" in ING[n][3] or "shellfish" in ING[n][3] or ING[n][5]) for n, *_ in items):
            labels.append("pescatarian")
    if "gluten" not in allergens:
        labels.append("gluten_free")
    if "dairy" not in allergens:
        labels.append("dairy_free")
    if "nuts" not in allergens:
        labels.append("nut_free")
    return sorted(allergens), labels, total


def build_recipe(title, desc, cuisine, method, time, servings, items, steps):
    allergens, labels, total = derive(items)
    nutrition = {k: round(v / servings, 1) for k, v in total.items()}
    tags = [cuisine, method]
    if time <= 25:
        tags.append("quick")
    if nutrition["protein_g"] >= 25:
        tags.append("high-protein")
    names = [n for n, *_ in items]
    return dict(
        title=title,
        description=desc,
        cuisine=cuisine,
        time_minutes=time,
        servings=servings,
        items=[dict(name=n, qty=q, unit=u, essential=e) for n, q, u, e in items],
        steps=steps,
        tags=tags,
        diet_labels=labels,
        allergens=allergens,
        nutrition=nutrition,
        search_text=" ".join([title] + names + tags),
    )


def expand_templates():
    recipes = []
    for t in TEMPLATES:
        for pi, prot in enumerate(t["proteins"]):
            pname, pqty = prot[0], prot[1]
            punit = prot[2] if len(prot) > 2 else "g"
            for vi in range(t["veg_variants"]):
                items = [(pname, pqty, punit, True)] + [tuple(b) for b in t["base"]]
                veg_word = None
                if t["veg_pool"]:
                    pool = t["veg_pool"]
                    veg = pool[(pi + vi * 2) % len(pool)]
                    veg2 = pool[(pi + vi * 2 + 1) % len(pool)]
                    vq, vu = t["veg_qty"]
                    items += [(veg, vq, vu, False), (veg2, vq, vu, False)]
                    veg_word = tw(veg)
                title = t["title"].format(p=tw(pname), v=veg_word or "")
                pl = pname
                vl = f"{veg} and {veg2}" if t["veg_pool"] else ""
                time = t["time"] + (pi % 3) * 5
                steps = [s.format(pl=pl, vl=vl) for s in t["steps"]]
                desc = t["desc"].format(pl=pl, vl=vl)
                recipes.append(
                    build_recipe(title, desc, t["cuisine"], t["method"], time,
                                 t["servings"], items, steps)
                )
    return recipes


def main():
    OUT_DIR.mkdir(exist_ok=True)

    ingredients = [
        dict(name=n, category=c, aliases=a, allergens=al, vegan=v, vegetarian=vg,
             default_unit=u, grams_per_unit=gpu,
             per_100g=dict(calories=k, protein_g=p, carbs_g=cb, fat_g=f))
        for n, c, a, al, v, vg, u, gpu, k, p, cb, f in INGREDIENTS
    ]

    recipes = [
        build_recipe(r["title"], r["desc"], r["cuisine"], r["method"],
                     r["time"], r["servings"], r["items"], r["steps"])
        for r in FIXED
    ] + expand_templates()

    titles = [r["title"] for r in recipes]
    assert len(titles) == len(set(titles)), "duplicate recipe titles"

    subs = [
        dict(ingredient=a, substitute=b, ratio=r, confidence=c, diet_ok=d)
        for a, b, r, c, d in SUBSTITUTIONS
    ]

    (OUT_DIR / "ingredients.json").write_text(json.dumps(ingredients, indent=1))
    (OUT_DIR / "recipes.json").write_text(json.dumps(recipes, indent=1))
    (OUT_DIR / "substitutions.json").write_text(json.dumps(subs, indent=1))
    print(f"Wrote {len(ingredients)} ingredients, {len(recipes)} recipes, "
          f"{len(subs)} substitutions to {OUT_DIR}")


if __name__ == "__main__":
    main()
