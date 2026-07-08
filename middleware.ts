import { auth } from "@/auth";
import { NextResponse } from "next/server";

function isAllowedEmail(email?: string | null) {
  if (!email) return false;
  const domain = email.split("@").at(1)?.toLowerCase();
  const allowed = (process.env.BITS_ALLOWED_DOMAINS ?? "bits-pilani.ac.in")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  return !!domain && allowed.some((item) => domain === item || domain.endsWith(`.${item}`));
}

export default auth((req) => {
  const path = req.nextUrl.pathname;
  const isProtected = path.startsWith("/analyze") || path.startsWith("/history");
  const isApi = path.startsWith("/api/analyze");
  const email = req.auth?.user?.email;

  if ((isProtected || isApi) && !email) {
    return isApi
      ? NextResponse.json({ error: "Unauthorized" }, { status: 401 })
      : NextResponse.redirect(new URL("/", req.url));
  }

  if ((isProtected || isApi) && !isAllowedEmail(email)) {
    return isApi
      ? NextResponse.json({ error: "BITS Pilani email required." }, { status: 403 })
      : NextResponse.redirect(new URL("/", req.url));
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/analyze/:path*", "/history/:path*", "/api/analyze/:path*"],
};
