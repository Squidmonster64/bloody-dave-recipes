#!/usr/bin/env node
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');

const root = path.resolve(__dirname, '..');
let source = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const marker = "\n$$('.tabs button').forEach(button => button.addEventListener";
const markerIndex = source.indexOf(marker);
assert(markerIndex > 0, 'Could not isolate pure application functions');
source = source.slice(0, markerIndex);
source += '\nglobalThis.__test={state,normaliseRecipe,searchable,mergedIngredients,itemStatus,parseMinutes,parseIngredientString,isFavourite};';

const storage = new Map();
const context = {
  console,
  localStorage: {
    getItem: key => storage.has(key) ? storage.get(key) : null,
    setItem: (key, value) => storage.set(key, value)
  },
  navigator: { userAgent: '' },
  window: { matchMedia: () => ({ matches: false }), navigator: {} },
  document: {}
};
vm.createContext(context);
vm.runInContext(source, context, { filename: 'app.js' });

const t = context.__test;
const payload = JSON.parse(fs.readFileSync(path.join(root, 'recipes.json'), 'utf8'));
t.state.baseRecipes = payload.recipes.map((recipe, index) => t.normaliseRecipe(recipe, index, false, false));
t.state.recipes = [...t.state.baseRecipes];

assert.ok(t.state.recipes.length >= 41);
assert.strictEqual(t.state.recipes.filter(t.isFavourite).length, t.state.recipes.filter(recipe => recipe.favouriteDefault).length);
assert.strictEqual(t.state.recipes.filter(recipe => recipe.structured).length, t.state.recipes.length);
assert.ok(t.state.recipes.every(recipe => /^BD-\d{4,}$/.test(recipe.id)));

const first = t.state.recipes[0];
assert.strictEqual(first.totalMinutes, 30);
assert.strictEqual(first.ingredients.length, 14);
assert.deepStrictEqual(JSON.parse(JSON.stringify(first.ingredients[0])), {
  name: 'Capsicum', quantity: '1', unit: '', pantry: false, notes: '', raw: '1 Capsicum'
});
assert.deepStrictEqual(JSON.parse(JSON.stringify(first.ingredients[2])), {
  name: 'Garlic', quantity: '2', unit: 'clove', pantry: false, notes: '', raw: '2 cloves Garlic'
});

assert(t.searchable(t.state.recipes[8]).includes('barramundi'));
assert(t.state.recipes.filter(recipe => recipe.totalMinutes > 0 && recipe.totalMinutes <= 20).length >= 4);

t.state.selected = new Set(['BD-0001', 'BD-0004']);
const merged = t.mergedIngredients();
const garlic = merged.find(item => item.key === 'garlic');
const oliveOil = merged.find(item => item.key === 'olive oil');
assert(garlic);
assert.deepStrictEqual(JSON.parse(JSON.stringify(garlic.quantities)), ['4 clove']);
assert(oliveOil && oliveOil.pantry === true);
assert.strictEqual(t.itemStatus(oliveOil), 'have');
assert.strictEqual(t.itemStatus(garlic), 'need');
assert.strictEqual(t.parseMinutes('1 hour 30 minutes'), 90);
assert.deepStrictEqual(JSON.parse(JSON.stringify(t.parseIngredientString('100g parmesan'))), {name:'parmesan', quantity:'100', unit:'g', pantry:false, notes:'', raw:'100g parmesan'});
assert.deepStrictEqual(JSON.parse(JSON.stringify(t.parseIngredientString('2 x 400g gnocchi'))), {name:'gnocchi', quantity:'800', unit:'g', pantry:false, notes:'', raw:'2 x 400g gnocchi'});
assert.deepStrictEqual(JSON.parse(JSON.stringify(t.parseIngredientString('400-500g beef sirloin steak'))), {name:'beef sirloin steak', quantity:'400-500', unit:'g', pantry:false, notes:'', raw:'400-500g beef sirloin steak'});

console.log('OK: data normalisation, favourites, time parsing, search and ingredient merging.');
