import { NextResponse } from "next/server";

/** Auth temporarily disabled — all routes open. */
export default function middleware() {
  return NextResponse.next();
}

export const config = {
  matcher: [],
};
