"use strict";

const BUILD_ID = "__BUILD_ID__";
const CACHE_NAME = `pokemon-go-collection-${BUILD_ID}`;
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

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
  if (event.data?.type === "GET_BUILD_ID") event.ports?.[0]?.postMessage({ build_id: BUILD_ID, cache_name: CACHE_NAME });
  if (event.data?.type === "CLEAN_OLD_CACHES") event.waitUntil(cleanOldCaches());
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
          return (await cache.match(event.request, { ignoreSearch: true })) || (isNavigation ? cache.match("./") : undefined);
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
