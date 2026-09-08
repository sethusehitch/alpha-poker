// Caddy terminates TLS before forwarding HTTP to Vinext. Only known public
// hosts are promoted to HTTPS; never trust client-supplied forwarding headers.
const tlsHosts = new Set([
  "alphapoker.io", "www.alphapoker.io", "alpha-poker.32.186.80.108.sslip.io",
]);

/** @param {string} requestUrl */
export function publicRequestUrl(requestUrl) {
  const url = new URL(requestUrl);
  if (tlsHosts.has(url.hostname) && (!url.port || url.port === "80")) {
    url.protocol = "https:";
    url.port = "";
  }
  return url;
}

/** @param {Request} request */
export function samePublicOrigin(request) {
  return request.headers.get("origin") === publicRequestUrl(request.url).origin;
}
