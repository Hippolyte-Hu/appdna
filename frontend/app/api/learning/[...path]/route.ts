import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
const SERVICE = "http://127.0.0.1:8788";
const ID = "[a-f0-9]{32}";
const readable = new RegExp(`^(video-sources(?:/${ID})?|tutorials(?:/${ID})?|desktop|assets/${ID}/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_.-]+\\.(?:mp4|mov|webm|mkv|jpg|png|blend))$`);
const writable = new RegExp(`^(video-sources/${ID}/executions|tutorials/${ID}/(?:run|stop))$`);

async function bridge(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  const writing = request.method === "POST";
  if (!(writing ? writable : readable).test(path)) {
    return Response.json({ detail: "Learning resource not found" }, { status: 404 });
  }
  const origin = request.headers.get("origin");
  if (writing && origin && origin !== `${request.nextUrl.protocol}//${request.headers.get("host")}`) {
    return Response.json({ detail: "Cross-origin desktop control is not allowed" }, { status: 403 });
  }
  try {
    if (writing && path.endsWith("/run")) {
      // Do not compete with the existing AppDNA assessment executor.
      const response = await fetch("http://127.0.0.1:8787/api/projects", { cache: "no-store", signal: AbortSignal.timeout(5000) });
      if (!response.ok) throw new Error("Could not check desktop availability");
      const projects: { status: string }[] = await response.json();
      if (projects.some(project => !["completed", "failed"].includes(project.status))) {
        return Response.json({ detail: "A Motion2Action assessment is using the desktop. Wait for it to finish." }, { status: 409 });
      }
    }
    const headers = new Headers();
    for (const name of ["content-type", "range"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    const response = await fetch(`${SERVICE}/${path.startsWith("assets/") ? "" : "api/"}${path}${request.nextUrl.search}`, {
      method: request.method, headers, body: writing ? await request.text() : undefined,
      cache: "no-store", signal: AbortSignal.timeout(15000), redirect: "error",
    });
    const resultHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const name of ["content-type", "content-disposition", "content-length", "content-range", "accept-ranges"]) {
      const value = response.headers.get(name);
      if (value) resultHeaders.set(name, value);
    }
    return new Response(response.body, { status: response.status, headers: resultHeaders });
  } catch {
    return Response.json({ detail: "Learning service unavailable. Check the local video-learning service and retry. A timed-out start may still be running; inspect its receipt before starting again." }, { status: 503 });
  }
}

export { bridge as GET, bridge as POST };
