import { BrowserRouter } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { AppRoutes } from "@/app/routes";
import { Header } from "@/components/layout/Header";

export default function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <div className="min-h-screen flex flex-col">
          <Header />
          <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
            <AppRoutes />
          </main>
        </div>
      </BrowserRouter>
    </AppProviders>
  );
}
