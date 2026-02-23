import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import DashboardLayout from "./layouts/DashboardLayout";
import AssessmentListPage from "./pages/AssessmentListPage";
import NewAssessmentPage from "./pages/NewAssessmentPage";
import AssessmentDetailPage from "./pages/AssessmentDetailPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<DashboardLayout />}>
          <Route index element={<Navigate to="/assessments" replace />} />
          <Route path="assessments" element={<AssessmentListPage />} />
          <Route path="assessments/new" element={<NewAssessmentPage />} />
          <Route path="assessments/:id" element={<AssessmentDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
