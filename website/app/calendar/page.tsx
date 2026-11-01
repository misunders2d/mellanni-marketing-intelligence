import type { Metadata } from "next";
import { DigestMonthList } from "@/components/digest-month-list";
import { getPublishedDigests } from "@/lib/supabase-public";

export const metadata: Metadata = {
  title: "Archive by month",
  description: "Browse Mellanni Marketing Intelligence weekly digests by publication month.",
};

export const dynamic = "force-dynamic";

export default async function CalendarPage() {
  const digests = await getPublishedDigests();

  return (
    <div className="shell interior-page">
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">Browse by date</p>
          <h1>Archive by month.</h1>
        </div>
        <p>Every published edition, newest first, grouped by the month it was published.</p>
      </header>
      <DigestMonthList digests={digests} />
    </div>
  );
}
