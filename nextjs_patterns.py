# ============================================================
# NEXT.JS PATTERNS & SNIPPETS KNOWLEDGE BASE
# ============================================================

NEXTJS_KNOWLEDGE = [
    # ── Project Structure ──────────────────────────────────
    {
        "id": "nextjs_project_structure",
        "category": "project_structure",
        "title": "Next.js 14 App Router project structure",
        "content": """
Next.js 14 App Router recommended structure:

my-next-app/
├── app/
│   ├── layout.tsx           # Root layout (applies to all pages)
│   ├── page.tsx             # Home page  /
│   ├── globals.css
│   ├── (auth)/              # Route group — no URL segment
│   │   ├── login/page.tsx   # /login
│   │   └── register/page.tsx
│   ├── dashboard/
│   │   ├── layout.tsx       # Dashboard-specific layout
│   │   ├── page.tsx         # /dashboard
│   │   └── [id]/page.tsx    # /dashboard/123
│   └── api/                 # Route Handlers (replaces pages/api)
│       └── auth/[...nextauth]/route.ts
├── components/
│   ├── ui/                  # Reusable dumb components
│   └── features/            # Feature-specific components
├── lib/
│   ├── api.ts               # Fetch wrappers for your FastAPI
│   ├── auth.ts              # Auth helpers
│   └── utils.ts
├── hooks/                   # Custom React hooks
├── types/                   # TypeScript interfaces
├── public/
├── .env.local
└── next.config.js
""",
    },
    # ── Root Layout ───────────────────────────────────────
    {
        "id": "nextjs_root_layout",
        "category": "boilerplate",
        "title": "Next.js root layout with providers",
        "content": """
// app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { QueryProvider } from "@/components/providers/QueryProvider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "My App",
  description: "Built with Next.js + FastAPI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <QueryProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
""",
    },
    # ── API Client ────────────────────────────────────────
    {
        "id": "nextjs_api_client",
        "category": "api",
        "title": "Next.js API client to call FastAPI backend",
        "content": """
// lib/api.ts
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function fetchWithAuth(path: string, options: RequestInit = {}) {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail ?? "API Error");
  }

  return res.json();
}

export const api = {
  get:    (path: string) => fetchWithAuth(path),
  post:   (path: string, body: unknown) => fetchWithAuth(path, { method: "POST",   body: JSON.stringify(body) }),
  put:    (path: string, body: unknown) => fetchWithAuth(path, { method: "PUT",    body: JSON.stringify(body) }),
  delete: (path: string)                => fetchWithAuth(path, { method: "DELETE" }),
};
""",
    },
    # ── Server Component Data Fetching ────────────────────
    {
        "id": "nextjs_server_component",
        "category": "data_fetching",
        "title": "Next.js Server Component — fetch from FastAPI",
        "content": """
// app/dashboard/page.tsx  — Server Component (default in App Router)
import { cookies } from "next/headers";

async function getItems() {
  const cookieStore = cookies();
  const token = cookieStore.get("access_token")?.value;

  const res = await fetch(`${process.env.API_URL}/api/v1/items`, {
    headers: { Authorization: `Bearer ${token}` },
    next: { revalidate: 60 },   // ISR — revalidate every 60s
  });

  if (!res.ok) throw new Error("Failed to fetch items");
  return res.json();
}

export default async function DashboardPage() {
  const items = await getItems();   // Runs on server, no useEffect needed

  return (
    <main>
      <h1>Dashboard</h1>
      <ul>
        {items.map((item: any) => (
          <li key={item.id}>{item.title}</li>
        ))}
      </ul>
    </main>
  );
}
""",
    },
    # ── Client Component + React Query ────────────────────
    {
        "id": "nextjs_react_query",
        "category": "data_fetching",
        "title": "Next.js Client Component with React Query + FastAPI",
        "content": """
// components/features/ItemList.tsx
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function ItemList() {
  const queryClient = useQueryClient();

  const { data: items, isLoading } = useQuery({
    queryKey: ["items"],
    queryFn: () => api.get("/items"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/items/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["items"] }),
  });

  if (isLoading) return <p>Loading...</p>;

  return (
    <ul>
      {items?.map((item: any) => (
        <li key={item.id}>
          {item.title}
          <button onClick={() => deleteMutation.mutate(item.id)}>Delete</button>
        </li>
      ))}
    </ul>
  );
}
""",
    },
    # ── Middleware ────────────────────────────────────────
    {
        "id": "nextjs_middleware",
        "category": "auth",
        "title": "Next.js middleware for route protection",
        "content": """
// middleware.ts (root of project)
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_ROUTES = ["/login", "/register", "/"];

export function middleware(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;
  const { pathname } = request.nextUrl;

  const isPublic = PUBLIC_ROUTES.some(route => pathname.startsWith(route));

  if (!token && !isPublic) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (token && (pathname === "/login" || pathname === "/register")) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
""",
    },
    # ── Route Handler ─────────────────────────────────────
    {
        "id": "nextjs_route_handler",
        "category": "api",
        "title": "Next.js Route Handler (App Router API routes)",
        "content": """
// app/api/items/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const limit = searchParams.get("limit") ?? "20";

  const res = await fetch(`${process.env.API_URL}/api/v1/items?limit=${limit}`, {
    headers: { Authorization: `Bearer ${process.env.INTERNAL_API_KEY}` },
  });

  const data = await res.json();
  return NextResponse.json(data);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  // validate, then forward to FastAPI
  const res = await fetch(`${process.env.API_URL}/api/v1/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: 201 });
}
""",
    },
]