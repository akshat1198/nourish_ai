CREATE TABLE IF NOT EXISTS recipes (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  ingredients JSONB NOT NULL,     -- [{name, qty, unit, essential}]
  steps TEXT[] NOT NULL,
  tags TEXT[],
  nutrition JSONB                  -- {calories, protein, ...}
);

INSERT INTO recipes (title, ingredients, steps, tags, nutrition) VALUES
('Tomato Garlic Pasta',
 '[{"name":"pasta","qty":200,"unit":"g","essential":true},
   {"name":"tomato","qty":2,"unit":"pcs","essential":true},
   {"name":"garlic","qty":3,"unit":"cloves","essential":true},
   {"name":"olive oil","qty":2,"unit":"tbsp","essential":false}]',
 ARRAY['Boil pasta','Sauté garlic','Add tomatoes','Toss together'],
 ARRAY['vegan','quick','stovetop'],
 '{"calories":520}');
