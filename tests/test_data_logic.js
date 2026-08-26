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
source += '\nglobalThis.__test={state,normaliseRecipe,searchable,mergedIngredients,itemStatus,parseMinutes,parseIngredientString,isFavourite,heroAssetUrl,HERO_ASSET_VERSION,HERO_FOCAL,detailHero};';

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

assert.strictEqual(t.state.recipes.length, 41);
assert.strictEqual(t.state.recipes.filter(t.isFavourite).length, 41);
assert.strictEqual(t.state.recipes.filter(recipe => recipe.structured).length, 41);

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

const beefRump = t.state.recipes.find(recipe => recipe.id === 'BD-0012');
assert(beefRump);
assert.strictEqual(beefRump.heroImage, `assets/hero/BD-0012.jpg?v=${t.HERO_ASSET_VERSION}`);
assert.strictEqual(beefRump.heroFocal, '42% 48%');
assert.strictEqual(t.heroAssetUrl('BD-0001'), `assets/hero/BD-0001.jpg?v=${t.HERO_ASSET_VERSION}`);

const heroPaths = t.state.recipes.map(recipe => recipe.heroImage);
assert.strictEqual(heroPaths.length, 41);
assert(heroPaths.every(path => /^assets\/hero\/BD-\d{4}\.jpg\?v=\d+$/.test(path)));
assert.strictEqual(new Set(heroPaths).size, 41);

t.state.recipes.forEach(recipe => {
  assert.strictEqual(recipe.heroFocal, t.HERO_FOCAL[recipe.id] || '50% 50%');
  const markup = t.detailHero(recipe);
  assert(markup.includes('class="detail-hero"'));
  assert(markup.includes('--hero-focal:'));
  assert(markup.includes(recipe.heroImage));
});

const archiveOnly = t.normaliseRecipe({ id: 'HF-9999', title: 'Archive only' }, 0, true, false);
assert.strictEqual(archiveOnly.heroImage, '');
assert(t.detailHero(archiveOnly).includes('detail-hero-placeholder'));

const missingHero = t.detailHero({ ...beefRump, heroImage: '' });
assert(missingHero.includes('detail-hero-placeholder'));
assert(!missingHero.includes('<img'));

console.log('OK: data normalisation, favourites, time parsing, search and ingredient merging.');
console.log('OK: hero path resolution, unique mappings, focal defaults and placeholder fallback.');
