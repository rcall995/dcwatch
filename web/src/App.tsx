import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import NavBar from "@/components/NavBar";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Leaderboard from "@/pages/Leaderboard";
import PoliticianDetail from "@/pages/PoliticianDetail";
import TradeDetail from "@/pages/TradeDetail";
import Search from "@/pages/Search";
import About from "@/pages/About";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 30 * 60 * 1000, // 30 minutes (formerly cacheTime)
      refetchOnWindowFocus: false,
      retry: 2,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/politician/:name" element={<PoliticianDetail />} />
            <Route path="/trade/:id" element={<TradeDetail />} />
            <Route path="/search" element={<Search />} />
            <Route path="/about" element={<About />} />
          </Routes>
        </Layout>
        <NavBar />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
