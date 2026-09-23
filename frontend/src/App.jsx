import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext.jsx";
import RequireRole from "./auth/RequireRole.jsx";
import ActivityLog from "./pages/admin/ActivityLog.jsx";
import AdminHome from "./pages/admin/AdminHome.jsx";
import AgentMemory from "./pages/admin/AgentMemory.jsx";
import AllUsers from "./pages/admin/AllUsers.jsx";
import DecisionsInbox from "./pages/admin/DecisionsInbox.jsx";
import Overview from "./pages/admin/Overview.jsx";
import UserDetail from "./pages/admin/UserDetail.jsx";
import Login from "./pages/auth/Login.jsx";
import Signup from "./pages/auth/Signup.jsx";
import DriverHome from "./pages/driver/DriverHome.jsx";
import DriverProfile from "./pages/driver/DriverProfile.jsx";
import Landing from "./pages/Landing.jsx";
import PantryHome from "./pages/pantry/PantryHome.jsx";
import PantryProfile from "./pages/pantry/PantryProfile.jsx";
import NewOffer from "./pages/restaurant/NewOffer.jsx";
import OfferDetail from "./pages/restaurant/OfferDetail.jsx";
import RestaurantHome from "./pages/restaurant/RestaurantHome.jsx";
import RestaurantProfile from "./pages/restaurant/RestaurantProfile.jsx";

/**
 * App — the root component. Decides which page to show for each URL.
 *
 * AuthProvider wraps everything so any page can ask "who is logged in?" (useAuth()).
 * RequireRole guards the role dashboards so, e.g., a driver can't open /admin.
 */
export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/restaurant"
            element={
              <RequireRole roles={["restaurant"]}>
                <RestaurantHome />
              </RequireRole>
            }
          />
          <Route
            path="/restaurant/profile"
            element={
              <RequireRole roles={["restaurant"]}>
                <RestaurantProfile />
              </RequireRole>
            }
          />
          <Route
            path="/restaurant/offers/new"
            element={
              <RequireRole roles={["restaurant"]}>
                <NewOffer />
              </RequireRole>
            }
          />
          <Route
            path="/restaurant/offers/:offerId"
            element={
              <RequireRole roles={["restaurant"]}>
                <OfferDetail />
              </RequireRole>
            }
          />
          <Route
            path="/pantry"
            element={
              <RequireRole roles={["pantry"]}>
                <PantryHome />
              </RequireRole>
            }
          />
          <Route
            path="/pantry/profile"
            element={
              <RequireRole roles={["pantry"]}>
                <PantryProfile />
              </RequireRole>
            }
          />
          <Route
            path="/driver"
            element={
              <RequireRole roles={["driver"]}>
                <DriverHome />
              </RequireRole>
            }
          />
          <Route
            path="/driver/profile"
            element={
              <RequireRole roles={["driver"]}>
                <DriverProfile />
              </RequireRole>
            }
          />
          <Route
            path="/admin"
            element={
              <RequireRole roles={["admin"]}>
                <Overview />
              </RequireRole>
            }
          />
          <Route
            path="/admin/offers"
            element={
              <RequireRole roles={["admin"]}>
                <AdminHome />
              </RequireRole>
            }
          />
          <Route
            path="/admin/activity"
            element={
              <RequireRole roles={["admin"]}>
                <ActivityLog />
              </RequireRole>
            }
          />
          <Route
            path="/admin/decisions"
            element={
              <RequireRole roles={["admin"]}>
                <DecisionsInbox />
              </RequireRole>
            }
          />
          <Route
            path="/admin/users"
            element={
              <RequireRole roles={["admin"]}>
                <AllUsers />
              </RequireRole>
            }
          />
          <Route
            path="/admin/users/:userId"
            element={
              <RequireRole roles={["admin"]}>
                <UserDetail />
              </RequireRole>
            }
          />
          <Route
            path="/admin/memory"
            element={
              <RequireRole roles={["admin"]}>
                <AgentMemory />
              </RequireRole>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
