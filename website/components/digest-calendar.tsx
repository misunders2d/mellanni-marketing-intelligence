"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Digest } from "@/lib/digests";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function parseIsoDate(date: string) {
  const [year, month, day] = date.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function dateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return year + "-" + month + "-" + day;
}

function addMonths(date: Date, amount: number) {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function monthCells(month: Date) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = new Date(first.getFullYear(), first.getMonth(), 1 - mondayOffset);
  return Array.from({ length: 42 }, (_, index) =>
    new Date(start.getFullYear(), start.getMonth(), start.getDate() + index),
  );
}

export function DigestCalendar({ digests }: { digests: readonly Digest[] }) {
  const newestDate = digests[0]?.date;
  const [visibleMonth, setVisibleMonth] = useState(() =>
    newestDate ? parseIsoDate(newestDate) : new Date(),
  );
  const cells = useMemo(() => monthCells(visibleMonth), [visibleMonth]);
  const digestByDate = useMemo(() => {
    const grouped = new Map<string, Digest[]>();
    for (const digest of digests) {
      const items = grouped.get(digest.date) ?? [];
      items.push(digest);
      grouped.set(digest.date, items);
    }
    return grouped;
  }, [digests]);
  const label = new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
  }).format(visibleMonth);
  const currentMonth = visibleMonth.getMonth();
  const today = dateKey(new Date());

  return (
    <section className="calendar" aria-labelledby="calendar-heading">
      <div className="calendar-toolbar">
        <div>
          <p className="eyebrow">Publication calendar</p>
          <h2 id="calendar-heading" aria-live="polite">{label}</h2>
        </div>
        <div className="calendar-actions" aria-label="Calendar month controls">
          <button
            type="button"
            className="secondary-button"
            onClick={() => setVisibleMonth((month) => addMonths(month, -1))}
            aria-label="Show previous month"
          >
            <span aria-hidden="true">←</span> Previous
          </button>
          <button
            type="button"
            className="secondary-button calendar-today"
            onClick={() => setVisibleMonth(new Date())}
          >
            Today
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => setVisibleMonth((month) => addMonths(month, 1))}
            aria-label="Show next month"
          >
            Next <span aria-hidden="true">→</span>
          </button>
        </div>
      </div>

      <div className="calendar-shell">
        <table>
          <caption className="visually-hidden">Digest publication dates for {label}</caption>
          <thead>
            <tr>
              {WEEKDAYS.map((day) => (
                <th scope="col" key={day}>
                  <span className="weekday-full">{day}</span>
                  <span className="weekday-short" aria-hidden="true">{day.slice(0, 1)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 6 }, (_, week) => (
              <tr key={week}>
                {cells.slice(week * 7, week * 7 + 7).map((date) => {
                  const key = dateKey(date);
                  const entries = digestByDate.get(key) ?? [];
                  const isOutsideMonth = date.getMonth() !== currentMonth;
                  const isToday = key === today;
                  const primary = entries[0];

                  return (
                    <td
                      key={key}
                      className={isOutsideMonth ? "outside-month" : undefined}
                      data-today={isToday || undefined}
                    >
                      {primary ? (
                        <Link
                          className="calendar-digest-link"
                          href={"/digests/" + primary.slug}
                          aria-label={"Open “" + primary.title + "” published " + key}
                        >
                          <span className="calendar-day">{date.getDate()}</span>
                          <span className="calendar-digest-title">{primary.title}</span>
                          {entries.length > 1 ? (
                            <span className="calendar-more">+{entries.length - 1} more</span>
                          ) : null}
                        </Link>
                      ) : (
                        <span className="calendar-day">{date.getDate()}</span>
                      )}
                      {isToday ? <span className="visually-hidden">Today</span> : null}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="calendar-legend">
        <span aria-hidden="true" /> Dates with a green marker link to a published digest.
      </p>
    </section>
  );
}
