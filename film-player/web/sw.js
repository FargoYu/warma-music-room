/* Cache the artwork after the first visit, so a song's stills and UI sprites
   are fetched once.  Every cached URL is stamped by tools/build_data3.py, so a
   rebuilt asset is a different URL and this cache never answers stale - but the
   old stamps are only evicted when VERSION changes, so bump it now and then.

   Audio and video are deliberately not cached here: browsers fetch media with a
   Range header, the reply is 206, and Cache.put rejects partial responses - the
   cache-first path would die silently.  Their stamped URLs plus the HTTP cache
   do that job instead. */
const VERSION = "warma-4";   // every asset URL was restamped in this build
const CACHE = VERSION + "-art";

self.addEventListener("install", function () { self.skipWaiting(); });

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf(VERSION) !== 0; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (!/\/assets\/(pic|ui)\//.test(url.pathname)) return;
  e.respondWith(caches.open(CACHE).then(function (c) {
    return c.match(e.request).then(function (hit) {
      if (hit) return hit;
      return fetch(e.request).then(function (res) {
        if (res.ok) c.put(e.request, res.clone());
        return res;
      });
    });
  }));
});
