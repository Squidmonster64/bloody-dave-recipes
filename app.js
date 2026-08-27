const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const STORAGE = {
  selected: 'bd:selected:v4',
  favouriteOverrides: 'bd:favourite-overrides:v4',
  itemStatuses: 'bd:item-statuses:v4',
  legacyHave: 'bd:have:v2',
  promoted: 'bd:promoted-recipes:v4',
  weekPlan: 'bd:week-plan:v1',
  cookedAt: 'bd:cooked-at:v1',
  savedRecipes: 'bd:saved-recipes:v1'
};

const state = {
  baseRecipes: [],
  recipes: [],
  archive: [],
  archiveAvailable: false,
  archiveSelected: new Set(),
  selected: new Set(readJson(STORAGE.selected, [])),
  favouriteOverrides: readJson(STORAGE.favouriteOverrides, {}),
  itemStatuses: readJson(STORAGE.itemStatuses, {}),
  promotedRaw: readJson(STORAGE.promoted, []),
  weekPlan: readJson(STORAGE.weekPlan, {}),
  cookedAt: readJson(STORAGE.cookedAt, {}),
  savedRecipes: readJson(STORAGE.savedRecipes, []),
  currentView: 'library',
  lastListView: 'library',
  currentRecipe: null
};

const UNIT_ALIASES = new Map(Object.entries({
  packet: 'packet', packets: 'packet', pack: 'packet', packs: 'packet',
  sachet: 'sachet', sachets: 'sachet', bag: 'bag', bags: 'bag',
  tub: 'tub', tubs: 'tub', tin: 'tin', tins: 'tin', can: 'tin', cans: 'tin',
  clove: 'clove', cloves: 'clove', bunch: 'bunch', bunches: 'bunch',
  head: 'head', heads: 'head', stalk: 'stalk', stalks: 'stalk',
  knob: 'knob', knobs: 'knob', cup: 'cup', cups: 'cup',
  tsp: 'tsp', teaspoon: 'tsp', teaspoons: 'tsp',
  tbsp: 'tbsp', tablespoon: 'tbsp', tablespoons: 'tbsp',
  g: 'g', gram: 'g', grams: 'g', kg: 'kg', ml: 'ml', l: 'L',
  pinch: 'pinch', pinches: 'pinch', drizzle: 'drizzle', drizzles: 'drizzle',
  splash: 'splash', splashes: 'splash', piece: 'piece', pieces: 'piece',
  slice: 'slice', slices: 'slice', serve: 'serve', serves: 'serve'
}));

const INGREDIENT_ALIASES = new Map(Object.entries({
  scallions: 'spring onion', 'green onions': 'spring onion', 'green onion': 'spring onion',
  'spring onions': 'spring onion', 'red onions': 'red onion', 'brown onions': 'brown onion',
  'garlic cloves': 'garlic', 'garlic clove': 'garlic', 'olive oils': 'olive oil',
  'vegetable oils': 'vegetable oil', 'soy sauces': 'soy sauce', 'fish sauces': 'fish sauce',
  chillies: 'chilli', chilies: 'chilli', 'red chillies': 'red chilli', 'red chilies': 'red chilli',
  'coriander leaves': 'coriander', cilantro: 'coriander',
  carrots: 'carrot', tomatoes: 'tomato', potatoes: 'potato', capsicums: 'capsicum',
  cucumbers: 'cucumber', lemons: 'lemon', limes: 'lime', apples: 'apple', avocados: 'avocado',
  mushrooms: 'mushroom', shallots: 'shallot', onions: 'onion', eggs: 'egg',
  'spring onion greens': 'spring onion', 'spring onion whites': 'spring onion'
}));

function readJson(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    if (value === null) return fallback;
    const parsed = JSON.parse(value);
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function persist() {
  localStorage.setItem(STORAGE.selected, JSON.stringify([...state.selected]));
  localStorage.setItem(STORAGE.favouriteOverrides, JSON.stringify(state.favouriteOverrides));
  localStorage.setItem(STORAGE.itemStatuses, JSON.stringify(state.itemStatuses));
  localStorage.setItem(STORAGE.promoted, JSON.stringify(state.promotedRaw));
  localStorage.setItem(STORAGE.weekPlan, JSON.stringify(state.weekPlan));
  localStorage.setItem(STORAGE.cookedAt, JSON.stringify(state.cookedAt));
  localStorage.setItem(STORAGE.savedRecipes, JSON.stringify(state.savedRecipes));
}

function migrateLegacyHave() {
  if (Object.keys(state.itemStatuses).length) return;
  const legacy = readJson(STORAGE.legacyHave, []);
  for (const key of legacy) state.itemStatuses[key] = 'have';
  if (legacy.length) persist();
}

function localId(prefix = 'local') {
  return `${prefix}-${crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
}

function normaliseSavedRecipe(raw, { preserveId = false } = {}) {
  const now = new Date().toISOString();
  return {
    id: preserveId && raw?.id ? String(raw.id) : localId('saved'),
    title: String(raw?.title || '').trim().slice(0, 160),
    url: String(raw?.url || raw?.sourceUrl || '').trim().slice(0, 1000),
    tags: asArray(raw?.tags).map(value => String(value).trim().slice(0, 60)).filter(Boolean).slice(0, 20),
    notes: String(raw?.notes || '').trim().slice(0, 4000),
    createdAt: raw?.createdAt || now,
    updatedAt: raw?.updatedAt || now
  };
}

function savedRecipeLink(url) {
  try {
    const parsed = new URL(url);
    return /^https?:$/.test(parsed.protocol) ? parsed.href : '';
  } catch {
    return '';
  }
}

function norm(value) {
  return (value ?? '')
    .toString()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’']/g, "'")
    .trim();
}

function escapeHtml(value) {
  return (value ?? '').toString().replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  })[char]);
}

function firstDefined(...values) {
  const found = values.find(value => value !== undefined && value !== null && value !== '');
  return found !== undefined ? found : values[values.length - 1];
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (value === undefined || value === null || value === '') return [];
  return [value];
}

function bool(value, fallback = false) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  if (typeof value === 'string') {
    if (/^(true|yes|y|1|favourite|favorite)$/i.test(value.trim())) return true;
    if (/^(false|no|n|0)$/i.test(value.trim())) return false;
  }
  return fallback;
}

function parseMinutes(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const text = norm(value);
  if (!text) return 0;
  if (/^\d+(?:\.\d+)?$/.test(text)) return Number(text);
  const hours = /([0-9]+(?:\.[0-9]+)?)\s*(?:hours?|hrs?|h)\b/.exec(text);
  const minutes = /([0-9]+(?:\.[0-9]+)?)\s*(?:minutes?|mins?|m)\b/.exec(text);
  if (hours || minutes) return Math.round((hours ? Number(hours[1]) * 60 : 0) + (minutes ? Number(minutes[1]) : 0));
  const firstNumber = /([0-9]+(?:\.[0-9]+)?)/.exec(text);
  return firstNumber ? Number(firstNumber[1]) : 0;
}

function parseQuantity(value) {
  const text = norm(value).replace(/[–—]/g, '-');
  if (!text) return null;
  if (/^\d+(?:\.\d+)?$/.test(text)) return Number(text);
  const fraction = /^(\d+)\/(\d+)$/.exec(text);
  if (fraction) return Number(fraction[1]) / Number(fraction[2]);
  const mixed = /^(\d+)\s+(\d+)\/(\d+)$/.exec(text);
  if (mixed) return Number(mixed[1]) + Number(mixed[2]) / Number(mixed[3]);
  return null;
}

function formatNumber(value) {
  return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);
}

function normaliseUnit(unit) {
  const key = norm(unit).replace(/\.$/, '');
  return UNIT_ALIASES.get(key) || key;
}

function parseIngredientString(raw, pantryDefault = false) {
  const text = String(raw ?? '').trim();
  if (!text) return { name: '', quantity: '', unit: '', pantry: pantryDefault, notes: '', raw: text };

  const cleaned = text.replace(/[–—]/g, '-').replace(/\s+/g, ' ').trim();
  const unitPattern = '(kg|g|ml|l|cups?|tsp|teaspoons?|tbsp|tablespoons?|packets?|packs?|sachets?|bags?|tubs?|tins?|cans?|cloves?|bunch(?:es)?|heads?|stalks?|knobs?|pinch(?:es)?|drizzles?|splashes?|pieces?|slices?|serves?)';

  // Product-pack forms such as "2 x 800g potatoes" or "2 x 300g dumplings".
  let match = new RegExp(`^(\\d+(?:\\.\\d+)?)\\s*[x×]\\s*(\\d+(?:\\.\\d+)?)\\s*${unitPattern}\\b\\s*(?:\\([^)]*\\)\\s*)?(.+)$`, 'i').exec(cleaned);
  if (match) {
    const total = Number(match[1]) * Number(match[2]);
    return { name: match[4].trim(), quantity: formatNumber(total), unit: normaliseUnit(match[3]), pantry: pantryDefault, notes: '', raw: text };
  }

  // Count-multiplier forms such as "3 x 2 vegetable stock cubes".
  match = /^(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s+(.+)$/.exec(cleaned);
  if (match) {
    const total = Number(match[1]) * Number(match[2]);
    return { name: match[3].trim(), quantity: formatNumber(total), unit: '', pantry: pantryDefault, notes: '', raw: text };
  }

  // Attached metric units, including ranges: "100g parmesan", "400-500g beef", "80ml (1/3 cup) oil".
  match = new RegExp(`^(\\d+(?:\\.\\d+)?(?:-\\d+(?:\\.\\d+)?)?)\\s*${unitPattern}\\b\\s*(?:\\([^)]*\\)\\s*)?(.+)$`, 'i').exec(cleaned);
  if (match) {
    return { name: match[3].trim(), quantity: match[1], unit: normaliseUnit(match[2]), pantry: pantryDefault, notes: '', raw: text };
  }

  // General quantity + optional recognised unit. Supports fractions and ranges.
  const quantityPattern = '(\\d+\\s+\\d+\\/\\d+|\\d+\\/\\d+|\\d+(?:\\.\\d+)?(?:-\\d+(?:\\.\\d+)?)?)';
  match = new RegExp(`^${quantityPattern}\\s+(.+)$`).exec(cleaned);
  if (!match) return { name: cleaned, quantity: '', unit: '', pantry: pantryDefault, notes: '', raw: text };

  const quantity = match[1];
  const remainder = match[2].trim();
  const tokens = remainder.split(/\s+/);
  const possibleUnit = normaliseUnit(tokens[0]);
  const recognisedUnit = UNIT_ALIASES.has(norm(tokens[0]).replace(/\.$/, ''));
  const unit = recognisedUnit ? possibleUnit : '';
  const name = recognisedUnit ? tokens.slice(1).join(' ') : remainder;
  return { name: name || remainder, quantity, unit, pantry: pantryDefault, notes: '', raw: text };
}

function normaliseIngredient(raw, pantryDefault = false) {
  if (typeof raw === 'string') return parseIngredientString(raw, pantryDefault);
  const ingredient = raw || {};
  const rawText = firstDefined(ingredient.raw, ingredient.display, '');
  if (!firstDefined(ingredient.name, ingredient.ingredient, ingredient.item, ingredient.title) && rawText) {
    return parseIngredientString(rawText, pantryDefault);
  }
  return {
    name: firstDefined(ingredient.name, ingredient.ingredient, ingredient.item, ingredient.title, '').toString().trim(),
    quantity: firstDefined(ingredient.quantity, ingredient.qty, ingredient.amount, '').toString().trim(),
    unit: normaliseUnit(firstDefined(ingredient.unit, ingredient.measure, ingredient.measurement, '').toString().trim()),
    pantry: bool(firstDefined(ingredient.pantry, ingredient.isPantry, ingredient.fromPantry), pantryDefault),
    notes: firstDefined(ingredient.notes, ingredient.note, '').toString().trim(),
    raw: rawText.toString()
  };
}

function normaliseMethod(raw) {
  return asArray(raw).map((step, index) => {
    if (typeof step === 'string') return { number: index + 1, title: '', text: step };
    return {
      number: firstDefined(step.number, step.step, index + 1),
      title: firstDefined(step.title, step.heading, '').toString(),
      text: firstDefined(step.text, step.instruction, step.body, step.description, '').toString()
    };
  }).filter(step => step.text || step.title);
}

function normaliseRecipe(raw, index = 0, archive = false, localPromoted = false) {
  const explicitIngredients = asArray(firstDefined(raw.ingredients, raw.items));
  const buy = asArray(firstDefined(raw.buy, raw.buyIngredients, raw.shoppingIngredients));
  const pantry = asArray(firstDefined(raw.pantry, raw.pantryIngredients, raw.pantryItems));
  const ingredients = [
    ...explicitIngredients.map(item => normaliseIngredient(item, false)),
    ...buy.map(item => normaliseIngredient(item, false)),
    ...pantry.map(item => normaliseIngredient(item, true))
  ].filter(item => item.name);

  const prepMinutes = parseMinutes(firstDefined(raw.prepMinutes, raw.prepTime, raw.prep_time, raw.prep_mins));
  const cookMinutes = parseMinutes(firstDefined(raw.cookMinutes, raw.cookTime, raw.cook_time, raw.cook_mins));
  const explicitTotal = parseMinutes(firstDefined(raw.totalMinutes, raw.totalTime, raw.total_time, raw.readyInMinutes, raw.readyIn));
  const totalMinutes = explicitTotal || ((prepMinutes || cookMinutes) ? prepMinutes + cookMinutes : 0);
  const id = firstDefined(raw.id, raw.recipeId, raw.bdId, raw.archive_id, raw.slug, `${archive ? 'ARCHIVE' : 'BD-MISSING'}-${index + 1}`);
  const stableId = String(id);
  const tags = asArray(firstDefined(raw.tags, raw.labels, raw.categories)).map(String);
  const subtitle = firstDefined(raw.subtitle, raw.description, raw.tagline, '').toString();
  const defaultHeroImage = !archive && /^BD-\d{4,}$/.test(stableId) ? `assets/hero/${stableId}.jpg` : '';
  const defaultCardPdf = !archive && /^BD-\d{4,}$/.test(stableId) ? `cards/${stableId}.pdf` : '';
  const heroImage = firstDefined(raw.heroImage, raw.image, raw.imageUrl, raw.hero_image, raw.image_path, defaultHeroImage).toString();
  const cardPdf = firstDefined(raw.cardPdf, raw.card_pdf, raw.recipeCardPdf, defaultCardPdf).toString();

  return {
    raw,
    id: stableId,
    title: firstDefined(raw.title, raw.name, 'Untitled recipe').toString(),
    subtitle,
    source: firstDefined(raw.source, raw.provider, raw.origin, archive ? 'Archive' : "Bloody Dave's").toString(),
    sourceUrl: firstDefined(raw.sourceUrl, raw.url, raw.source_url, '').toString(),
    cuisine: firstDefined(raw.cuisine, raw.cuisineType, '').toString(),
    protein: firstDefined(raw.protein, raw.mainProtein, raw.proteinType, '').toString(),
    difficulty: firstDefined(raw.difficulty, '').toString(),
    tags,
    serves: firstDefined(raw.serves, raw.servings, raw.people, '').toString(),
    prepMinutes,
    cookMinutes,
    totalMinutes,
    rawPrepTime: firstDefined(raw.prep_time, raw.prepTime, ''),
    rawCookTime: firstDefined(raw.cook_time, raw.cookTime, ''),
    rawTotalTime: firstDefined(raw.total_time, raw.totalTime, ''),
    favouriteDefault: bool(firstDefined(raw.favourite, raw.favorite, raw.isFavourite, raw.isFavorite, raw.favouriteDefault, raw.favoriteDefault), !archive),
    heroImage,
    cardPdf,
    heroImageSubject: firstDefined(raw.hero_image_subject, raw.heroImageSubject, '').toString(),
    markdown: firstDefined(raw.reference_file, raw.markdown, raw.markdownFile, raw.recipeMarkdown, raw.md, '').toString(),
    ingredients,
    method: normaliseMethod(firstDefined(raw.method, raw.steps, raw.instructions)),
    allergens: asArray(firstDefined(raw.allergens, raw.allergenInfo)).map(String),
    nutrition: firstDefined(raw.nutrition_display, raw.nutritionDisplay, raw.nutrition, raw.nutritionInfo, '').toString(),
    notes: firstDefined(raw.notes, raw.cardNotes, raw.recipe_notes, '').toString(),
    libraryStatus: firstDefined(raw.library_status, raw.libraryStatus, '').toString(),
    archive,
    localPromoted,
    structured: ingredients.length > 0 || asArray(firstDefined(raw.method, raw.steps, raw.instructions)).length > 0
  };
}

function searchable(recipe) {
  return norm([
    recipe.id, recipe.title, recipe.subtitle, recipe.cuisine, recipe.source, recipe.protein,
    recipe.difficulty, recipe.tags.join(' '), recipe.ingredients.map(item => `${item.name} ${item.notes} ${item.raw}`).join(' '),
    recipe.rawPrepTime, recipe.rawCookTime, recipe.rawTotalTime, recipe.prepMinutes, recipe.cookMinutes, recipe.totalMinutes,
    recipe.totalMinutes ? `${recipe.totalMinutes} min ${recipe.totalMinutes} minutes` : '', recipe.heroImageSubject
  ].join(' '));
}

function canonicalIngredientName(name) {
  const key = norm(name)
    .replace(/\([^)]*\)/g, ' ')
    .replace(/\b(fresh|finely|roughly|thinly|sliced|diced|chopped|minced|crushed|grated|peeled|trimmed|to serve|for serving)\b/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return INGREDIENT_ALIASES.get(key) || key;
}

function displayIngredient(item) {
  const amount = [item.quantity, item.unit].filter(Boolean).join(' ');
  return `${amount ? `${amount} ` : ''}${item.name}${item.notes ? `, ${item.notes}` : ''}`.trim();
}

function isFavourite(recipe) {
  if (Object.prototype.hasOwnProperty.call(state.favouriteOverrides, recipe.id)) {
    return Boolean(state.favouriteOverrides[recipe.id]);
  }
  return recipe.favouriteDefault;
}

function toggleFavourite(recipe) {
  state.favouriteOverrides[recipe.id] = !isFavourite(recipe);
  persist();
  renderLibrary();
  if (state.currentRecipe?.id === recipe.id) renderDetail(recipe);
}

async function fetchJson(path, { optional = false } = {}) {
  try {
    const response = await fetch(path, { cache: 'no-cache' });
    if (!response.ok) {
      if (optional && response.status === 404) return null;
      throw new Error(`${path}: HTTP ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    if (optional) return null;
    throw error;
  }
}

async function loadCuratedPayload() {
  try {
    return await fetchJson('recipes.json');
  } catch (rootError) {
    try {
      return await fetchJson('data/recipes.json');
    } catch {
      throw rootError;
    }
  }
}

async function loadData() {
  migrateLegacyHave();
  const rawRecipes = await loadCuratedPayload();
  const recipeRecords = Array.isArray(rawRecipes) ? rawRecipes : firstDefined(rawRecipes.recipes, rawRecipes.items, []);
  state.baseRecipes = recipeRecords.map((recipe, index) => normaliseRecipe(recipe, index, false, false));
  const promoted = asArray(state.promotedRaw).map((recipe, index) => normaliseRecipe(recipe, index, false, true));
  state.recipes = [...state.baseRecipes, ...promoted];

  const validIds = new Set(state.recipes.map(recipe => recipe.id));
  state.selected = new Set([...state.selected].filter(id => validIds.has(id)));

  const rawArchive = await fetchJson('Archive/index.json', { optional: true });
  if (rawArchive) {
    const archiveRecords = Array.isArray(rawArchive) ? rawArchive : firstDefined(rawArchive.recipes, rawArchive.items, []);
    state.archive = archiveRecords.map((recipe, index) => normaliseRecipe(recipe, index, true, false));
    state.archiveAvailable = true;
  } else {
    state.archive = [];
    state.archiveAvailable = false;
  }

  validateLoadedData(rawRecipes);
  persist();
  routeFromHash();
}

function validateLoadedData(payload) {
  const warnings = [];
  const ids = new Set();
  const duplicateIds = new Set();
  for (const recipe of state.baseRecipes) {
    if (ids.has(recipe.id)) duplicateIds.add(recipe.id);
    ids.add(recipe.id);
  }
  if (state.baseRecipes.length < 41) warnings.push(`Loaded ${state.baseRecipes.length} curated recipes; expected at least the historical library of 41.`);
  if (payload && !Array.isArray(payload) && payload.recipe_count !== undefined && Number(payload.recipe_count) !== state.baseRecipes.length) {
    warnings.push(`recipes.json declares ${payload.recipe_count} recipes but contains ${state.baseRecipes.length}.`);
  }
  if (duplicateIds.size) warnings.push(`Duplicate recipe IDs: ${[...duplicateIds].join(', ')}.`);
  const invalidIds = state.baseRecipes.filter(recipe => !/^BD-\d{4,}$/.test(recipe.id));
  if (invalidIds.length) warnings.push(`${invalidIds.length} recipe record(s) do not use the expected BD-0001 style ID.`);
  const warning = $('#dataWarning');
  warning.classList.toggle('hidden', warnings.length === 0);
  warning.textContent = warnings.join(' ');
}

function setView(name, { updateHash = true } = {}) {
  state.currentView = name;
  if (name !== 'detail') state.lastListView = name;
  $$('.view').forEach(view => view.classList.toggle('active', view.id === `${name}View`));
  $$('.tabs button').forEach(button => button.classList.toggle('active', button.dataset.view === name));
  const detail = name === 'detail';
  $('#mainTabs').classList.toggle('hidden', detail);
  $('#backBtn').classList.toggle('hidden', !detail);
  if (updateHash && !detail) history.pushState(null, '', `#${name}`);
  if (name === 'shopping') renderShopping();
  if (name === 'archive') renderArchive();
  if (name === 'saved') renderSavedRecipes();
}

function routeFromHash() {
  const hash = location.hash.replace(/^#/, '');
  if (hash.startsWith('recipe/')) {
    const id = decodeURIComponent(hash.slice('recipe/'.length));
    const recipe = [...state.recipes, ...state.archive].find(item => item.id === id);
    if (recipe) {
      openRecipe(recipe, { updateHash: false });
      return;
    }
  }
  const view = ['library', 'archive', 'shopping', 'saved'].includes(hash) ? hash : 'library';
  setView(view, { updateHash: false });
  renderAll();
}

function placeholderMark(recipe) {
  const words = recipe.title.split(/\s+/).filter(Boolean);
  return words.slice(0, 2).map(word => word[0]).join('').toUpperCase() || 'BD';
}

function applyCardImage(node, recipe) {
  const image = $('.card-image', node);
  const placeholder = $('.card-placeholder', node);
  $('.placeholder-protein', node).textContent = recipe.protein || recipe.cuisine || 'Recipe';
  $('.placeholder-mark', node).textContent = placeholderMark(recipe);
  if (!recipe.heroImage) return;
  image.src = recipe.heroImage;
  image.alt = recipe.heroImageSubject || recipe.title;
  image.classList.remove('hidden');
  placeholder.classList.add('hidden');
  image.onerror = () => {
    image.classList.add('hidden');
    placeholder.classList.remove('hidden');
  };
}

function recipeCard(recipe, { archive = false } = {}) {
  const node = $('#recipeCardTemplate').content.firstElementChild.cloneNode(true);
  applyCardImage(node, recipe);
  $('.source', node).textContent = recipe.source || "Bloody Dave's";
  $('.title', node).textContent = recipe.title;
  $('.subtitle', node).textContent = recipe.subtitle || recipe.tags.slice(0, 3).join(' · ') || (recipe.structured ? 'Full structured recipe' : 'Reference recipe');
  $('.meta', node).textContent = [
    recipe.id, recipe.cuisine, recipe.protein, recipe.totalMinutes ? `${recipe.totalMinutes} min` : 'Time not recorded'
  ].filter(Boolean).join(' · ');

  $$('.open', node).forEach(button => button.addEventListener('click', () => openRecipe(recipe)));

  const favourite = $('.favourite', node);
  if (archive) {
    favourite.remove();
  } else {
    favourite.textContent = isFavourite(recipe) ? '★' : '☆';
    favourite.classList.toggle('on', isFavourite(recipe));
    favourite.addEventListener('click', event => {
      event.stopPropagation();
      toggleFavourite(recipe);
    });
  }

  const select = $('.select-recipe', node);
  const selectLabel = select.parentElement;
  if (archive) {
    selectLabel.lastChild.textContent = ' Promote';
    select.checked = state.archiveSelected.has(recipe.id);
    select.addEventListener('change', () => {
      select.checked ? state.archiveSelected.add(recipe.id) : state.archiveSelected.delete(recipe.id);
      renderArchiveActions();
    });
  } else {
    select.checked = state.selected.has(recipe.id);
    select.addEventListener('change', () => {
      select.checked ? state.selected.add(recipe.id) : state.selected.delete(recipe.id);
      persist();
      updateCount();
    });
  }
  return node;
}

function sortedRecipes(recipes) {
  const order = $('#sortOrder').value;
  return [...recipes].sort((a, b) => {
    if (order === 'title') return a.title.localeCompare(b.title);
    if (order === 'source') return a.source.localeCompare(b.source) || a.title.localeCompare(b.title);
    if (order === 'time') {
      const ta = a.totalMinutes || Number.POSITIVE_INFINITY;
      const tb = b.totalMinutes || Number.POSITIVE_INFINITY;
      return ta - tb || a.title.localeCompare(b.title);
    }
    return a.id.localeCompare(b.id, undefined, { numeric: true });
  });
}

function renderLibrary() {
  const query = norm($('#librarySearch').value);
  const favouritesOnly = $('#favouritesOnly').checked;
  const maxMinutes = Number($('#timeFilter').value || 0);
  const filtered = sortedRecipes(state.recipes.filter(recipe => {
    return (!query || searchable(recipe).includes(query))
      && (!favouritesOnly || isFavourite(recipe))
      && (!maxMinutes || (recipe.totalMinutes > 0 && recipe.totalMinutes <= maxMinutes));
  }));
  $('#libraryGrid').replaceChildren(...filtered.map(recipe => recipeCard(recipe)));
  const favourites = state.recipes.filter(isFavourite).length;
  const structured = state.baseRecipes.filter(recipe => recipe.structured).length;
  const promotedText = state.promotedRaw.length ? ` · ${state.promotedRaw.length} local promotion${state.promotedRaw.length === 1 ? '' : 's'}` : '';
  $('#libraryStatus').textContent = `${filtered.length} of ${state.recipes.length} recipes · ${favourites} favourites · ${structured} with structured ingredients/method${promotedText}`;
}

function renderArchiveActions() {
  const count = state.archiveSelected.size;
  $('#archiveSelectionCount').textContent = count;
  $('#archiveActions').classList.toggle('hidden', count === 0);
}

function renderArchive() {
  const query = norm($('#archiveSearch').value);
  if (!state.archiveAvailable) {
    $('#archiveStatus').textContent = 'Archive not installed. The curated library works independently. Add Archive/index.json later and reload; no app rebuild is required. New recipes are published through Recipe Studio.';
    $('#archiveGrid').replaceChildren();
    $('#archiveActions').classList.add('hidden');
    return;
  }
  const filtered = state.archive.filter(recipe => !query || searchable(recipe).includes(query));
  $('#archiveGrid').replaceChildren(...filtered.slice(0, 300).map(recipe => recipeCard(recipe, { archive: true })));
  $('#archiveStatus').textContent = `${filtered.length} archive matches${filtered.length > 300 ? ' · showing first 300' : ''}`;
  renderArchiveActions();
}

function inlineMarkdown(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

function markdownToHtml(markdown) {
  const safe = escapeHtml(markdown).replace(/\r\n/g, '\n');
  const lines = safe.split('\n');
  let html = '';
  let inList = false;
  let listType = '';
  const closeList = () => {
    if (inList) html += `</${listType}>`;
    inList = false;
    listType = '';
  };
  for (const line of lines) {
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    const ordered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const unordered = /^\s*[-*]\s+(.*)$/.exec(line);
    const image = /^!\[(.*?)\]\((.*?)\)$/.exec(line.trim());
    if (heading) {
      closeList();
      const level = Math.min(heading[1].length + 1, 6);
      html += `<h${level}>${inlineMarkdown(heading[2])}</h${level}>`;
    } else if (image) {
      closeList();
      html += `<p class="source-image-reference"><strong>Source image reference:</strong> ${inlineMarkdown(image[1])}</p>`;
    } else if (ordered || unordered) {
      const nextType = ordered ? 'ol' : 'ul';
      if (!inList || listType !== nextType) {
        closeList();
        listType = nextType;
        inList = true;
        html += `<${listType}>`;
      }
      html += `<li>${inlineMarkdown((ordered || unordered)[1])}</li>`;
    } else if (!line.trim()) {
      closeList();
    } else {
      closeList();
      html += `<p>${inlineMarkdown(line)}</p>`;
    }
  }
  closeList();
  return html;
}

function detailHero(recipe) {
  if (recipe.heroImage) {
    return `<img class="detail-hero" src="${escapeHtml(recipe.heroImage)}" alt="${escapeHtml(recipe.heroImageSubject || recipe.title)}">`;
  }
  return `<div class="detail-hero-placeholder"><div><span>${escapeHtml(recipe.protein || recipe.cuisine || 'Bloody Dave recipe')}</span><strong>${escapeHtml(recipe.title)}</strong></div></div>`;
}

function ingredientSection(recipe) {
  const buy = recipe.ingredients.filter(item => !item.pantry);
  const pantry = recipe.ingredients.filter(item => item.pantry);
  if (!recipe.ingredients.length) return '<p class="empty">Structured ingredients are not yet present in the supplied dataset for this recipe.</p>';
  const list = items => `<ul class="ingredients">${items.map(item => `<li><span>${escapeHtml([item.quantity, item.unit].filter(Boolean).join(' '))}</span>${item.quantity || item.unit ? ' ' : ''}${escapeHtml(item.name)}${item.notes ? ` <small>${escapeHtml(item.notes)}</small>` : ''}</li>`).join('')}</ul>`;
  return `<div class="ingredient-columns"><div><h4>Buy</h4>${buy.length ? list(buy) : '<p class="empty">None listed.</p>'}</div><div><h4>Pantry</h4>${pantry.length ? list(pantry) : '<p class="empty">None listed.</p>'}</div></div>`;
}

async function renderDetail(recipe) {
  state.currentRecipe = recipe;
  const favouriteButton = recipe.archive ? '' : `<div class="detail-actions"><button id="detailFavourite" class="detail-favourite">${isFavourite(recipe) ? '★ Favourite' : '☆ Favourite'}</button><button id="markCooked" class="secondary">Mark cooked today</button></div>`;
  const tags = recipe.tags.length ? `<div class="tag-row">${recipe.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>` : '';
  const sourceNote = recipe.archive
    ? '<div class="archive-note">Archive record. It remains separate from the curated Bloody Dave library until promoted.</div>'
    : (!recipe.structured ? '<div class="data-note">This recipe is in the curated library, but its ingredients, method and time have not yet been transcribed into the current structured dataset. The supplied Markdown reference is shown below.</div>' : '');
  const method = recipe.method.length
    ? `<ol class="method">${recipe.method.map(step => `<li>${step.title ? `<strong>${escapeHtml(step.title)}</strong><br>` : ''}${escapeHtml(step.text)}</li>`).join('')}</ol>`
    : '<p class="empty">Structured method is not yet present in the supplied dataset.</p>';
  const cardActions = recipe.cardPdf
    ? `<div class="recipe-card-pdf-actions"><a class="button-link" href="${escapeHtml(recipe.cardPdf)}" target="_blank" rel="noopener">Open printable recipe card (PDF)</a><span class="subtle">2-page A4 landscape card</span></div>`
    : '';

  $('#recipeDetail').innerHTML = `
    ${detailHero(recipe)}
    <div class="detail-body">
      <div class="detail-title-row">
        <div><span class="pill">${escapeHtml(recipe.source)}</span><h2>${escapeHtml(recipe.title)}</h2><p>${escapeHtml(recipe.subtitle)}</p></div>
        ${favouriteButton}
      </div>
      <div class="detail-meta">
        <b>${escapeHtml(recipe.id)}</b>
        ${recipe.serves ? `<b>Serves ${escapeHtml(recipe.serves)}</b>` : ''}
        ${recipe.prepMinutes ? `<span>Prep ${recipe.prepMinutes} min</span>` : ''}
        ${recipe.cookMinutes ? `<span>Cook ${recipe.cookMinutes} min</span>` : ''}
        ${recipe.totalMinutes ? `<span>Total ${recipe.totalMinutes} min</span>` : '<span>Time not recorded</span>'}
        ${recipe.cuisine ? `<span>${escapeHtml(recipe.cuisine)}</span>` : ''}
        ${recipe.protein ? `<span>${escapeHtml(recipe.protein)}</span>` : ''}
        ${recipe.difficulty ? `<span>${escapeHtml(recipe.difficulty)}</span>` : ''}
      </div>
      ${tags}
      ${cardActions}
      ${sourceNote}
      <div class="detail-grid">
        <section><h3>Ingredients</h3>${ingredientSection(recipe)}</section>
        <section><h3>Method</h3>${method}</section>
      </div>
      ${recipe.allergens.length ? `<section><h3>Allergens</h3><p>${escapeHtml(recipe.allergens.join(', '))}</p></section>` : ''}
      ${recipe.nutrition ? `<section><h3>Nutrition</h3><p>${escapeHtml(recipe.nutrition)}</p></section>` : ''}
      ${recipe.notes ? `<section><h3>Notes</h3><p>${escapeHtml(recipe.notes)}</p></section>` : ''}
      ${recipe.sourceUrl ? `<p><a href="${escapeHtml(recipe.sourceUrl)}" target="_blank" rel="noopener">Original source</a></p>` : ''}
      <section id="markdownReference" class="markdown-reference hidden"><h3>Supporting recipe reference</h3><div id="markdownBody"></div></section>
    </div>`;

  const hero = $('.detail-hero');
  if (hero) hero.onerror = () => { hero.replaceWith(htmlToElement(detailHero({ ...recipe, heroImage: '' }))); };
  $('#detailFavourite')?.addEventListener('click', () => toggleFavourite(recipe));
  $('#markCooked')?.addEventListener('click', () => markCooked(recipe));

  if (recipe.markdown) {
    try {
      const response = await fetch(recipe.markdown);
      if (response.ok) {
        const markdown = await response.text();
        $('#markdownBody').innerHTML = markdownToHtml(markdown);
        $('#markdownReference').classList.remove('hidden');
      }
    } catch {
      // The structured record remains usable if a supporting Markdown file is unavailable.
    }
  }
}

function htmlToElement(html) {
  const template = document.createElement('template');
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

function openRecipe(recipe, { updateHash = true } = {}) {
  state.lastListView = recipe.archive ? 'archive' : state.currentView === 'shopping' ? 'shopping' : 'library';
  renderDetail(recipe);
  setView('detail', { updateHash: false });
  if (updateHash) history.pushState(null, '', `#recipe/${encodeURIComponent(recipe.id)}`);
  window.scrollTo({ top: 0, behavior: 'instant' });
}

function selectedRecipes() {
  return state.recipes.filter(recipe => state.selected.has(recipe.id));
}

function mergedIngredients() {
  const map = new Map();
  for (const recipe of selectedRecipes()) {
    for (const ingredient of recipe.ingredients) {
      const key = canonicalIngredientName(ingredient.name);
      if (!key) continue;
      const row = map.get(key) || {
        key,
        name: ingredient.name,
        pantry: true,
        recipes: new Set(),
        quantitiesByUnit: new Map(),
        looseQuantities: new Set()
      };
      row.pantry = row.pantry && ingredient.pantry;
      row.recipes.add(recipe.title);
      const parsed = parseQuantity(ingredient.quantity);
      const unit = normaliseUnit(ingredient.unit);
      if (parsed !== null) {
        row.quantitiesByUnit.set(unit, (row.quantitiesByUnit.get(unit) || 0) + parsed);
      } else {
        const loose = [ingredient.quantity, ingredient.unit].filter(Boolean).join(' ').trim();
        if (loose) row.looseQuantities.add(loose);
      }
      map.set(key, row);
    }
  }
  return [...map.values()].map(row => ({
    ...row,
    recipes: [...row.recipes],
    quantities: [
      ...[...row.quantitiesByUnit.entries()].map(([unit, quantity]) => `${formatNumber(quantity)}${unit ? ` ${unit}` : ''}`),
      ...row.looseQuantities
    ]
  })).sort((a, b) => a.name.localeCompare(b.name));
}

function itemStatus(item) {
  return state.itemStatuses[item.key] || (item.pantry ? 'have' : 'need');
}

function setItemStatus(item, status) {
  state.itemStatuses[item.key] = status;
  persist();
  renderShopping();
}

function statusToggle(item) {
  const wrap = document.createElement('div');
  wrap.className = 'status-toggle';
  const current = itemStatus(item);
  for (const status of ['need', 'have']) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `${status}${current === status ? ` active ${status}` : ''}`;
    button.textContent = status[0].toUpperCase() + status.slice(1);
    button.setAttribute('aria-pressed', current === status ? 'true' : 'false');
    button.addEventListener('click', () => setItemStatus(item, status));
    wrap.append(button);
  }
  return wrap;
}

function shoppingRow(item) {
  const row = document.createElement('div');
  row.className = 'shopping-item';
  const text = document.createElement('div');
  text.className = 'shopping-item-main';
  text.innerHTML = `<b>${escapeHtml(item.name)}${item.pantry ? '<span class="pantry-tag">PANTRY</span>' : ''}</b>${item.quantities.length ? `<span>${escapeHtml(item.quantities.join(' + '))}</span>` : ''}<br><small>${escapeHtml(item.recipes.join(', '))}</small>`;
  row.append(text, statusToggle(item));
  return row;
}

function empty(message) {
  const paragraph = document.createElement('p');
  paragraph.className = 'empty';
  paragraph.textContent = message;
  return paragraph;
}

function resetSavedRecipeForm() {
  $('#savedRecipeForm').reset();
  $('#savedRecipeId').value = '';
  $('#savedRecipeFormTitle').textContent = 'Keep a recipe link';
}

function renderSavedRecipes() {
  const query = norm($('#savedRecipeSearch').value);
  const rows = [...state.savedRecipes]
    .filter(recipe => !query || norm([recipe.title, recipe.url, recipe.notes, ...(recipe.tags || [])].join(' ')).includes(query))
    .sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
  const grid = $('#savedRecipeGrid');
  if (!rows.length) {
    grid.replaceChildren(empty(query ? 'No saved recipes match that search.' : 'No saved recipes yet. Keep a useful link or import a Pocket Cookbook backup.'));
    return;
  }
  const cards = rows.map(recipe => {
    const card = document.createElement('article');
    card.className = 'recipe-card saved-recipe-card';
    const body = document.createElement('div');
    body.className = 'card-body';
    const source = document.createElement('span');
    source.className = 'pill';
    source.textContent = 'Saved recipe';
    const title = document.createElement('h2');
    title.className = 'title';
    title.textContent = recipe.title;
    body.append(source, title);
    const href = savedRecipeLink(recipe.url);
    if (href) {
      const link = document.createElement('a');
      link.className = 'saved-recipe-source';
      link.href = href;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'Open source';
      body.append(link);
    } else if (recipe.url) {
      const url = document.createElement('p');
      url.className = 'subtle';
      url.textContent = recipe.url;
      body.append(url);
    }
    if (recipe.tags?.length) {
      const tags = document.createElement('div');
      tags.className = 'tag-row';
      recipe.tags.forEach(tag => {
        const chip = document.createElement('span');
        chip.className = 'tag';
        chip.textContent = tag;
        tags.append(chip);
      });
      body.append(tags);
    }
    if (recipe.notes) {
      const notes = document.createElement('p');
      notes.className = 'saved-recipe-notes';
      notes.textContent = recipe.notes;
      body.append(notes);
    }
    const updated = document.createElement('small');
    updated.textContent = `Updated ${new Date(recipe.updatedAt).toLocaleString('en-AU')}`;
    body.append(updated);
    const actions = document.createElement('div');
    actions.className = 'card-actions';
    const edit = document.createElement('button');
    edit.className = 'secondary';
    edit.dataset.editSavedRecipe = recipe.id;
    edit.textContent = 'Edit';
    const remove = document.createElement('button');
    remove.className = 'secondary';
    remove.dataset.deleteSavedRecipe = recipe.id;
    remove.textContent = 'Delete';
    actions.append(edit, remove);
    body.append(actions);
    card.append(body);
    return card;
  });
  grid.replaceChildren(...cards);
}

function exportSavedRecipes() {
  downloadText('bloody-daves-saved-recipes.json', JSON.stringify({ schema: 'bloody-daves/pocket-cookbook/v1', exportedAt: new Date().toISOString(), recipes: state.savedRecipes }, null, 2), 'application/json;charset=utf-8');
}

async function importSavedRecipes(file) {
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    if (data?.schema !== 'bloody-daves/pocket-cookbook/v1' || !Array.isArray(data.recipes)) throw new Error('incompatible');
    const additions = data.recipes.map(recipe => normaliseSavedRecipe(recipe)).filter(recipe => recipe.title);
    state.savedRecipes.push(...additions);
    persist();
    $('#savedRecipeStatus').textContent = `${additions.length} saved recipe${additions.length === 1 ? '' : 's'} imported as editable local copies.`;
    renderSavedRecipes();
  } catch {
    $('#savedRecipeStatus').textContent = 'That file is not a Pocket Cookbook backup.';
  }
}

function renderShopping() {
  const selected = selectedRecipes();
  const missingStructured = selected.filter(recipe => !recipe.ingredients.length);
  $('#selectedRecipes').innerHTML = selected.length
    ? `${selected.map(recipe => `<span class="selected-chip">${escapeHtml(recipe.id)} · ${escapeHtml(recipe.title)}</span>`).join('')}${missingStructured.length ? `<div class="data-note">${missingStructured.length} selected recipe${missingStructured.length === 1 ? '' : 's'} ha${missingStructured.length === 1 ? 's' : 've'} no structured ingredient list in the supplied dataset and therefore cannot contribute items yet.</div>` : ''}`
    : '<p class="empty">No recipes selected.</p>';

  const all = mergedIngredients();
  const pantry = all.filter(item => item.pantry);
  const nonPantry = all.filter(item => !item.pantry);
  const need = all.filter(item => itemStatus(item) === 'need');
  const have = nonPantry.filter(item => itemStatus(item) === 'have');

  $('#needList').replaceChildren(...(need.length ? need.map(shoppingRow) : [empty('Nothing needed.') ]));
  $('#haveList').replaceChildren(...(have.length ? have.map(shoppingRow) : [empty('Nothing marked Have.') ]));
  $('#pantryList').replaceChildren(...(pantry.length ? pantry.map(shoppingRow) : [empty('No pantry items in selected recipes.') ]));
  updateCount();
}

function updateCount() {
  $('#shoppingCount').textContent = state.selected.size ? `(${state.selected.size})` : '';
}

function startOfWeek(date = new Date()) {
  const value = new Date(date);
  const day = value.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  value.setDate(value.getDate() + offset);
  value.setHours(0, 0, 0, 0);
  return value;
}

function dateKey(date) {
  return date.toISOString().slice(0, 10);
}

function formatPlanDate(date) {
  return new Intl.DateTimeFormat('en-AU', { weekday: 'short', day: 'numeric', month: 'short' }).format(date);
}

function renderWeekPlan() {
  const host = $('#weekPlan');
  if (!host) return;
  const weekStart = startOfWeek();
  const selected = selectedRecipes();
  const options = state.recipes.filter(recipe => recipe.structured || recipe.ingredients.length);
  const fragment = document.createDocumentFragment();
  for (let index = 0; index < 7; index += 1) {
    const day = new Date(weekStart);
    day.setDate(weekStart.getDate() + index);
    const key = dateKey(day);
    const wrap = document.createElement('label');
    wrap.className = 'week-day';
    const name = document.createElement('strong');
    name.textContent = formatPlanDate(day);
    const select = document.createElement('select');
    select.setAttribute('aria-label', `Recipe for ${formatPlanDate(day)}`);
    const emptyOption = new Option('No recipe planned', '');
    select.add(emptyOption);
    for (const recipe of options) {
      const option = new Option(`${recipe.title}${recipe.totalMinutes ? ` · ${recipe.totalMinutes} min` : ''}`, recipe.id);
      option.selected = state.weekPlan[key] === recipe.id;
      select.add(option);
    }
    select.addEventListener('change', () => {
      if (select.value) state.weekPlan[key] = select.value;
      else delete state.weekPlan[key];
      persist();
      renderWeekPlan();
    });
    wrap.append(name, select);
    const planned = options.find(recipe => recipe.id === state.weekPlan[key]);
    const note = document.createElement('small');
    note.textContent = planned && state.cookedAt[planned.id]
      ? `Last cooked ${new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short' }).format(new Date(state.cookedAt[planned.id]))}`
      : (selected.includes(planned) ? 'Selected for the combined shopping list' : 'Stored only on this device');
    wrap.append(note);
    fragment.append(wrap);
  }
  host.replaceChildren(fragment);
}

function addSelectedToWeek() {
  const selected = selectedRecipes();
  if (!selected.length) {
    $('#weekPlanStatus').textContent = 'Select one or more recipes with the Shop control first.';
    return;
  }
  const weekStart = startOfWeek();
  const emptyDates = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(weekStart);
    day.setDate(weekStart.getDate() + index);
    return dateKey(day);
  }).filter(key => !state.weekPlan[key]);
  selected.slice(0, emptyDates.length).forEach((recipe, index) => { state.weekPlan[emptyDates[index]] = recipe.id; });
  persist();
  $('#weekPlanStatus').textContent = `${Math.min(selected.length, emptyDates.length)} recipe${Math.min(selected.length, emptyDates.length) === 1 ? '' : 's'} added to the first open days this week.`;
  renderWeekPlan();
}

function exportWeekPlan() {
  const recipes = state.recipes;
  const cards = Object.entries(state.weekPlan).map(([date, id]) => {
    const recipe = recipes.find(item => item.id === id);
    return recipe ? { date, type: 'recipe', label: recipe.title, recipeId: recipe.id, url: `${location.origin}#recipe/${encodeURIComponent(recipe.id)}` } : null;
  }).filter(Boolean);
  downloadText('bloody-daves-week-plan.json', JSON.stringify({ schema: 'bloody-daves/suite-transfer/v1', kind: 'week-plan', source: 'recipes', createdAt: new Date().toISOString(), payload: { weekOf: dateKey(startOfWeek()), cards } }, null, 2), 'application/json;charset=utf-8');
}

function exportGetListTransfer() {
  const items = mergedIngredients().filter(item => itemStatus(item) === 'need').map(item => ({
    name: item.name,
    quantity: item.quantities.join(' + '),
    category: item.pantry ? 'pantry' : 'general',
    sourceLabel: item.recipes.join(', ')
  }));
  downloadText('bloody-daves-recipes-to-get-list.json', JSON.stringify({ schema: 'bloody-daves/suite-transfer/v1', kind: 'shopping-list', source: 'recipes', createdAt: new Date().toISOString(), payload: { title: 'Recipe needs', items } }, null, 2), 'application/json;charset=utf-8');
}

function markCooked(recipe) {
  state.cookedAt[recipe.id] = new Date().toISOString();
  persist();
  renderDetail(recipe);
  renderWeekPlan();
}

function renderAll() {
  renderLibrary();
  renderArchive();
  renderShopping();
  renderSavedRecipes();
  renderWeekPlan();
  updateCount();
}

function nextBdNumber(existingIds) {
  const highest = existingIds.reduce((max, id) => {
    const match = /^BD-(\d+)$/.exec(id);
    return match ? Math.max(max, Number(match[1])) : max;
  }, 0);
  return highest + 1;
}

function archiveToCuratedRaw(recipe, id) {
  const buy = recipe.ingredients.filter(item => !item.pantry).map(displayIngredient);
  const pantry = recipe.ingredients.filter(item => item.pantry).map(displayIngredient);
  return {
    id,
    title: recipe.title,
    source: recipe.source,
    source_url: recipe.sourceUrl,
    serves: recipe.serves,
    prep_time: recipe.prepMinutes ? `${recipe.prepMinutes} minutes` : '',
    cook_time: recipe.cookMinutes ? `${recipe.cookMinutes} minutes` : '',
    total_time: recipe.totalMinutes ? `${recipe.totalMinutes} minutes` : '',
    cuisine: recipe.cuisine,
    protein: recipe.protein,
    difficulty: recipe.difficulty,
    tags: recipe.tags,
    favourite: false,
    library_status: 'promoted locally — add to source recipes.json for permanent deployment',
    reference_file: '',
    buy,
    pantry,
    method: recipe.method.map(step => step.text),
    allergens: recipe.allergens.join(', '),
    nutrition: recipe.nutrition,
    hero_image: recipe.heroImage,
    hero_image_subject: recipe.heroImageSubject
  };
}

function downloadText(filename, content, type = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 500);
}

function promoteSelectedArchive() {
  if (!state.archiveSelected.size) return;
  const selectedArchive = state.archive.filter(recipe => state.archiveSelected.has(recipe.id));
  const existingIds = [...state.recipes.map(recipe => recipe.id)];
  let next = nextBdNumber(existingIds);
  const additions = selectedArchive.map(recipe => archiveToCuratedRaw(recipe, `BD-${String(next++).padStart(4, '0')}`));
  state.promotedRaw.push(...additions);
  state.recipes.push(...additions.map((raw, index) => normaliseRecipe(raw, index, false, true)));
  state.archiveSelected.clear();
  persist();
  downloadText('bloody-dave-promotions.json', JSON.stringify({ schema_version: '5.0', recipe_count: additions.length, recipes: additions }, null, 2), 'application/json;charset=utf-8');
  renderAll();
  setView('library');
}

function installHelp() {
  const standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  if (standalone) {
    $('#installBtn').classList.add('hidden');
    return;
  }
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.finally(() => {
      deferredPrompt = null;
      $('#installBtn').classList.add('hidden');
    });
    return;
  }
  $('#installInstructions').innerHTML = isIOS || isSafari
    ? '<ol><li>Open this site in Safari.</li><li>Tap the Share button.</li><li>Choose <strong>Add to Home Screen</strong>.</li><li>Tap <strong>Add</strong>.</li></ol><p>The installed app opens full-screen and works offline after the first complete load.</p>'
    : '<ol><li>Open the browser menu.</li><li>Choose <strong>Install app</strong> or <strong>Add to Home screen</strong>.</li></ol><p>The installed app works offline after the first complete load.</p>';
  $('#installDialog').showModal();
}

$$('.tabs button').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
$('#savedRecipeForm').addEventListener('submit', event => {
  event.preventDefault();
  const title = $('#savedRecipeTitle').value.trim();
  if (!title) return;
  const existing = state.savedRecipes.find(recipe => recipe.id === $('#savedRecipeId').value);
  const saved = normaliseSavedRecipe({
    ...existing,
    title,
    url: $('#savedRecipeUrl').value,
    tags: $('#savedRecipeTags').value.split(',').map(value => value.trim()).filter(Boolean),
    notes: $('#savedRecipeNotes').value,
    createdAt: existing?.createdAt || new Date().toISOString(),
    updatedAt: new Date().toISOString()
  }, { preserveId: Boolean(existing) });
  state.savedRecipes = [...state.savedRecipes.filter(recipe => recipe.id !== saved.id), saved];
  persist();
  resetSavedRecipeForm();
  $('#savedRecipeStatus').textContent = existing ? 'Saved recipe updated locally.' : 'Saved recipe kept locally.';
  renderSavedRecipes();
});
$('#cancelSavedRecipe').addEventListener('click', resetSavedRecipeForm);
$('#savedRecipeSearch').addEventListener('input', renderSavedRecipes);
$('#exportSavedRecipes').addEventListener('click', exportSavedRecipes);
$('#importSavedRecipes').addEventListener('change', async event => {
  await importSavedRecipes(event.target.files?.[0]);
  event.target.value = '';
});
$('#savedRecipeGrid').addEventListener('click', event => {
  const editId = event.target.closest('[data-edit-saved-recipe]')?.dataset.editSavedRecipe;
  const deleteId = event.target.closest('[data-delete-saved-recipe]')?.dataset.deleteSavedRecipe;
  if (editId) {
    const recipe = state.savedRecipes.find(item => item.id === editId);
    if (!recipe) return;
    $('#savedRecipeId').value = recipe.id;
    $('#savedRecipeTitle').value = recipe.title;
    $('#savedRecipeUrl').value = recipe.url;
    $('#savedRecipeTags').value = (recipe.tags || []).join(', ');
    $('#savedRecipeNotes').value = recipe.notes;
    $('#savedRecipeFormTitle').textContent = 'Edit saved recipe';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  if (deleteId) {
    const recipe = state.savedRecipes.find(item => item.id === deleteId);
    if (!recipe || !confirm(`Delete “${recipe.title}”?`)) return;
    state.savedRecipes = state.savedRecipes.filter(item => item.id !== deleteId);
    persist();
    $('#savedRecipeStatus').textContent = 'Saved recipe deleted locally.';
    renderSavedRecipes();
  }
});
['librarySearch', 'favouritesOnly', 'timeFilter', 'sortOrder'].forEach(id => $(`#${id}`).addEventListener('input', renderLibrary));
$('#archiveSearch').addEventListener('input', renderArchive);
$('#clearSelection').addEventListener('click', () => {
  state.selected.clear();
  persist();
  renderAll();
});
$('#resetStatuses').addEventListener('click', () => {
  state.itemStatuses = {};
  persist();
  renderShopping();
});
$('#printNeed').addEventListener('click', () => window.print());
$('#exportNeed').addEventListener('click', () => {
  const lines = mergedIngredients()
    .filter(item => itemStatus(item) === 'need')
    .map(item => `☐ ${item.name}${item.quantities.length ? ` — ${item.quantities.join(' + ')}` : ''}${item.pantry ? ' [PANTRY]' : ''}`);
  const selected = selectedRecipes().map(recipe => `${recipe.id} — ${recipe.title}`);
  const content = `Bloody Dave's — Need List\n\nRecipes:\n${selected.map(item => `- ${item}`).join('\n') || '- None selected'}\n\nNeed:\n${lines.join('\n') || 'Nothing needed.'}\n`;
  downloadText('bloody-daves-need-list.txt', content);
});
$('#exportGetListTransfer').addEventListener('click', exportGetListTransfer);
$('#addSelectedToWeek').addEventListener('click', addSelectedToWeek);
$('#exportWeek').addEventListener('click', exportWeekPlan);
$('#promoteSelected').addEventListener('click', promoteSelectedArchive);
$('#clearArchiveSelection').addEventListener('click', () => {
  state.archiveSelected.clear();
  renderArchive();
});
$('#backBtn').addEventListener('click', () => {
  history.pushState(null, '', `#${state.lastListView || 'library'}`);
  routeFromHash();
});
window.addEventListener('hashchange', routeFromHash);

let deferredPrompt;
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  deferredPrompt = event;
});
$('#installBtn').addEventListener('click', installHelp);

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(console.error));
}

loadData().catch(error => {
  console.error(error);
  $('#libraryStatus').textContent = 'The curated recipe dataset could not be loaded. Serve the folder over HTTP and confirm recipes.json exists.';
  $('#dataWarning').textContent = error.message;
  $('#dataWarning').classList.remove('hidden');
});
