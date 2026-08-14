import { NextRequest, NextResponse } from 'next/server';

const AGENTS_BASE = process.env.NEXT_PUBLIC_AGENTS_API_URL || 'http://127.0.0.1:8000';
const PROXY_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes for long-running Clark queries

export const maxDuration = 300; // 5 min (Vercel/serverless limit; no-op in dev)

/**
 * Proxy to Clark (agents) backend with a long timeout so long-running queries
 * (backtest, multi-agent, etc.) don't hit "Internal Server Error" while the backend is still working.
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, params, 'GET');
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, params, 'POST');
}

export async function PUT(request: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, params, 'PUT');
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, params, 'PATCH');
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, params, 'DELETE');
}

async function proxy(
  request: NextRequest,
  params: Promise<{ path?: string[] }>,
  method: string
) {
  const { path } = await params;
  const pathSegments = path && path.length > 0 ? path.join('/') : '';
  const url = `${AGENTS_BASE}/api/v1/agents${pathSegments ? `/${pathSegments}` : ''}${request.nextUrl.search}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);

  try {
    const headers = new Headers();
    request.headers.forEach((value, key) => {
      if (key.toLowerCase() !== 'host' && key.toLowerCase() !== 'connection') {
        headers.set(key, value);
      }
    });

    const body = method !== 'GET' && method !== 'HEAD' ? await request.text() : undefined;

    let res: Response | null = null;
    let lastFetchError: unknown = null;

    // Retry fetch up to 2 attempts for transient socket disconnects/reloads
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        res = await fetch(url, {
          method,
          headers,
          body: body || undefined,
          signal: controller.signal,
        });
        break; // fetch succeeded
      } catch (err: unknown) {
        lastFetchError = err;
        if (attempt < 2 && !(err instanceof Error && err.name === 'AbortError')) {
          await new Promise((resolve) => setTimeout(resolve, 800));
        } else {
          throw err;
        }
      }
    }

    clearTimeout(timeoutId);

    if (!res) {
      throw lastFetchError || new Error('Fetch failed without response');
    }

    const contentType = res.headers.get('Content-Type') || 'application/json';

    // Pass the body through instead of buffering it.
    //
    // This used to be `await res.text()`, which reads the upstream response to
    // completion before replying. For JSON that is invisible; for the SSE
    // endpoint it is fatal — every progress event Clark emits would be held
    // here until the turn finished and then delivered in one burst, which is
    // precisely the behaviour streaming exists to remove. Streaming is correct
    // for both, so there is no content-type branch.
    const responseHeaders = new Headers({ 'Content-Type': contentType });
    if (contentType.includes('text/event-stream')) {
      responseHeaders.set('Cache-Control', 'no-cache, no-transform');
      // Tells nginx and Railway's edge not to buffer either; without it the
      // proxy in front of production reintroduces the same problem.
      responseHeaders.set('X-Accel-Buffering', 'no');
      responseHeaders.set('Connection', 'keep-alive');
    }

    return new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: responseHeaders,
    });
  } catch (e: unknown) {
    clearTimeout(timeoutId);
    console.error(`[Agents Proxy Error] Failed proxying ${method} ${url}:`, e);
    if (e instanceof Error && e.name === 'AbortError') {
      return NextResponse.json(
        {
          success: false,
          message: 'Request timed out. The query may still be running on the server—try again or use a simpler query.',
          agent_flow: { nodes: [], edges: [], execution_order: [] },
          costs: { query_cost: 0, session_cost: 0, overall_cost: 0 },
        },
        { status: 504 }
      );
    }
    return NextResponse.json(
      {
        success: false,
        message: 'Clark is temporarily unavailable. Please try again in a moment.',
        agent_flow: { nodes: [], edges: [], execution_order: [] },
        costs: { query_cost: 0, session_cost: 0, overall_cost: 0 },
      },
      { status: 502 }
    );
  }
}
