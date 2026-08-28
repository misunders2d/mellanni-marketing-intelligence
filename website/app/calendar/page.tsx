import type { Metadata } from "next";
import { DigestCalendar } from "@/components/digest-calendar";
import { getPublishedDigests } from "@/lib/supabase-public";

export const metadata: Metadata = {
  title: "Calendar",
  description: "Browse Mellanni Marketing Intelligence weekly digests by publication date.",
};

export const dynamic = "force-dynamic";

export default async function CalendarPage() {
  const digests = await getPublishedDigests();

  return (
    <div className="shell interior-page">
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">Browse by date</p>
          <h1>The publication calendar.</h1>
        </div>
        <p>
          Move month by month through the archive. Highlighted dates open the briefing published that week.
        </p>
      </header>
      <DigestCalendar digests={digests} />
    </div>
  );
}
