"use strict";

const BUILD_ID = "__BUILD_ID__";
const CACHE_NAME = `pokemon-go-collection-${BUILD_ID}`;
const FIELD_PACK_PREFIX = "pokemon-go-field-pack-";
const FIELD_PACK_RESOURCE_LIMIT = 256;
const PRECACHE = __PRECACHE__;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)));
});

self.addEventListener("activate", (event) => {
  // Old versioned caches are retained until a client explicitly asks for cleanup.
  // This lets a tab running an older content-hashed script finish requests against
  // the matching cached build instead of mixing old JavaScript with new data.
  event.waitUntil(self.clients.claim());
});

async function cleanOldCaches() {
  const keys = await caches.keys();
  await Promise.all(keys.filter((key) => key.startsWith("pokemon-go-collection-") && key !== CACHE_NAME).map((key) => caches.delete(key)));
}

function normalizeFieldPackId(value) {
  const id = String(value || "").trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9-]{0,47}$/.test(id)) throw new Error("Invalid field pack id");
  return id;
}

function normalizeFieldPackResources(values) {
  if (!Array.isArray(values) || values.length < 1 || values.length > FIELD_PACK_RESOURCE_LIMIT) {
    throw new Error(`Field packs require 1-${FIELD_PACK_RESOURCE_LIMIT} resources`);
  }
  const seen = new Set();
  const resources = [];
  for (const value of values) {
    const url = new URL(String(value || ""), self.location.href);
    if (url.origin !== self.location.origin) throw new Error("Field packs may cache same-origin resources only");
    if (url.searchParams.has("connectivity") || url.searchParams.has("diagnostics")) {
      throw new Error("Probe requests cannot be included in a field pack");
    }
    const normalized = `${url.pathname}${url.search}`;
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    resources.push(normalized);
  }
  if (!resources.length) throw new Error("Field pack contains no cacheable resources");
  return resources;
}

function fieldPackCachePrefix(id) {
  return `${FIELD_PACK_PREFIX}${id}-`;
}

function isCurrentBuildFieldPack(cacheName) {
  return cacheName.startsWith(FIELD_PACK_PREFIX) && cacheName.includes(`-${BUILD_ID}-`);
}

async function matchCurrentBuildFieldPack(request) {
  const keys = (await caches.keys()).filter(isCurrentBuildFieldPack).sort().reverse();
  for (const key of keys) {
    const cache = await caches.open(key);
    const response = await cache.match(request, { ignoreSearch: true });
    if (response) return response;
  }
  return undefined;
}

async function installFieldPack(data) {
  const id = normalizeFieldPackId(data?.pack_id);
  const resources = normalizeFieldPackResources(data?.resources);
  const token = `${BUILD_ID}-${Date.now().toString(36)}`;
  const cacheName = `${fieldPackCachePrefix(id)}${token}`;
  const cache = await caches.open(cacheName);
  try {
    await cache.addAll(resources);
    for (const resource of resources) {
      if (!(await cache.match(resource, { ignoreSearch: false }))) throw new Error(`Field pack verification failed for ${resource}`);
    }
  } catch (error) {
    await caches.delete(cacheName);
    throw error;
  }

  // The previous complete pack is retained until the replacement has fully cached
  // and verified. Only then are older versions of this named pack removed.
  const keys = await caches.keys();
  await Promise.all(keys
    .filter((key) => key.startsWith(fieldPackCachePrefix(id)) && key !== cacheName)
    .map((key) => caches.delete(key)));
  return { pack_id: id, build_id: BUILD_ID, cache_name: cacheName, resource_count: resources.length };
}

async function removeFieldPack(data) {
  const id = normalizeFieldPackId(data?.pack_id);
  const keys = await caches.keys();
  const matching = keys.filter((key) => key.startsWith(fieldPackCachePrefix(id)));
  await Promise.all(matching.map((key) => caches.delete(key)));
  return { pack_id: id, removed_cache_count: matching.length };
}

async function listFieldPacks() {
  const keys = await caches.keys();
  return keys.filter((key) => key.startsWith(FIELD_PACK_PREFIX)).sort();
}

function reply(event, payload) {
  event.ports?.[0]?.postMessage(payload);
}

self.addEventListener("message", (event) => {
  if (event.origin && event.origin !== self.location.origin) return;
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
  if (event.data?.type === "GET_BUILD_ID") reply(event, { build_id: BUILD_ID, cache_name: CACHE_NAME });
  if (event.data?.type === "CLEAN_OLD_CACHES") event.waitUntil(cleanOldCaches());
  if (event.data?.type === "INSTALL_FIELD_PACK") {
    event.waitUntil(installFieldPack(event.data)
      .then((result) => reply(event, { ok: true, ...result }))
      .catch((error) => reply(event, { ok: false, error: String(error?.message || error) })));
  }
  if (event.data?.type === "REMOVE_FIELD_PACK") {
    event.waitUntil(removeFieldPack(event.data)
      .then((result) => reply(event, { ok: true, ...result }))
      .catch((error) => reply(event, { ok: false, error: String(error?.message || error) })));
  }
  if (event.data?.type === "LIST_FIELD_PACKS") {
    event.waitUntil(listFieldPacks()
      .then((packs) => reply(event, { ok: true, packs }))
      .catch((error) => reply(event, { ok: false, error: String(error?.message || error) })));
  }
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  // Keep the canonical connectivity probe network-only. Tests and the offline
  // detector intentionally depend on this exact branch remaining independent.
  if (url.searchParams.has("connectivity")) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Diagnostics probes are also network-only, but remain a separate contract so
  // extending diagnostics cannot accidentally alter connectivity detection.
  if (url.searchParams.has("diagnostics")) {
    event.respondWith(fetch(event.request));
    return;
  }

  const requestedBuild = url.searchParams.get("v");
  if (requestedBuild && requestedBuild !== BUILD_ID) {
    event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
    return;
  }

  const isNavigation = event.request.mode === "navigate";
  const isData = url.pathname.includes("/data/");
  if (isNavigation || isData) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(async () => {
          const cache = await caches.open(CACHE_NAME);
          const current = await cache.match(event.request, { ignoreSearch: true });
          if (current) return current;
          const fieldPack = await matchCurrentBuildFieldPack(event.request);
          return fieldPack || (isNavigation ? cache.match("./") : undefined);
        }),
    );
    return;
  }

  event.respondWith(
    caches.match(event.request, { ignoreSearch: true }).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      });
    }),
  );
});
