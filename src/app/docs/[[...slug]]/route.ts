const DOCS_HOST = "kryptonfund.mintlify.dev";
const FORWARDED_HOST = "app.kryptonfund.com";
const FORWARDED_PROTO = "https";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

async function proxyToMintlify(request: Request): Promise<Response> {
  const proxyUrl = new URL(request.url);
  proxyUrl.protocol = "https:";
  proxyUrl.hostname = DOCS_HOST;
  proxyUrl.port = "";

  const proxyRequest = new Request(proxyUrl.toString(), request);
  const incomingHost =
    request.headers.get("X-Forwarded-Host") ??
    request.headers.get("host") ??
    FORWARDED_HOST;
  const incomingProto =
    request.headers.get("X-Forwarded-Proto") ??
    (new URL(request.url).protocol === "http:" ? "http" : "https");
  const forwardedHost =
    process.env.NODE_ENV === "production" ? FORWARDED_HOST : incomingHost;
  const forwardedProto =
    process.env.NODE_ENV === "production" ? FORWARDED_PROTO : incomingProto;

  proxyRequest.headers.set("Host", DOCS_HOST);
  proxyRequest.headers.set("X-Forwarded-Host", forwardedHost);
  proxyRequest.headers.set("X-Forwarded-Proto", forwardedProto);
  proxyRequest.headers.set("Accept-Encoding", "identity");

  try {
    return await fetch(proxyRequest);
  } catch {
    return new Response("Failed to load docs from Mintlify.", { status: 502 });
  }
}

export async function GET(request: Request) {
  return proxyToMintlify(request);
}

export async function POST(request: Request) {
  return proxyToMintlify(request);
}

export async function PUT(request: Request) {
  return proxyToMintlify(request);
}

export async function PATCH(request: Request) {
  return proxyToMintlify(request);
}

export async function DELETE(request: Request) {
  return proxyToMintlify(request);
}

export async function HEAD(request: Request) {
  return proxyToMintlify(request);
}

export async function OPTIONS(request: Request) {
  return proxyToMintlify(request);
}
