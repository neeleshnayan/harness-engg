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

    const res = await fetch(url, {
      method,
      headers,
      body: body || undefined,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const resBody = await res.text();
    return new NextResponse(resBody, {
      status: res.status,
      statusText: res.statusText,
      headers: {
        'Content-Type': res.headers.get('Content-Type') || 'application/json',
      },
    });
  } catch (e: unknown) {
    clearTimeout(timeoutId);
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
    throw e;
  }
}
