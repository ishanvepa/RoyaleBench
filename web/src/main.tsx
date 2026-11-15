import "@fontsource-variable/geist";
import "@fontsource-variable/plus-jakarta-sans";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { Providers } from "./app/providers";
import { createRouter } from "./app/routes";
import "./styles/index.css";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root).render(
  <StrictMode>
    <Providers>
      <RouterProvider router={createRouter()} />
    </Providers>
  </StrictMode>,
);
