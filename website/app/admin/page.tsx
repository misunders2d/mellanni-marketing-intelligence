import type { Metadata } from "next";
import { AdminConsole } from "@/components/admin-console";

export const metadata: Metadata = {
  title: "Admin",
  description: "Manage marketing intelligence sources and digest publication.",
};

export default function AdminPage() {
  return (
    <div className="shell interior-page admin-page">
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">Private workspace</p>
          <h1>Source desk.</h1>
        </div>
        <p>
          Manage which sources enter the local research run, then review draft digests before publication.
        </p>
      </header>
      <AdminConsole />
    </div>
  );
}
