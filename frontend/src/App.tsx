import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Console from './pages/Console';
import Dashboard from './pages/Dashboard';
import Activity from './pages/Activity';
import Concepts from './pages/Concepts';
import ChannelDetail from './pages/ChannelDetail';
import RunDetailPage from './pages/RunDetail';
import ImageReview from './pages/ImageReview';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Console />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/activity" element={<Activity />} />
            <Route path="/channels/:id" element={<ChannelDetail />} />
            <Route path="/concepts" element={<Concepts />} />
            <Route path="/review" element={<ImageReview />} />
            <Route path="/runs/:id" element={<RunDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
