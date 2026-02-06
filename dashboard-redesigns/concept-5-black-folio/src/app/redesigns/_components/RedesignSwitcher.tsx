import Link from "next/link";
import { REDESIGNS, RedesignId, getRedesignCycle } from "@/app/redesigns/_lib/designs";

type Props = {
  active: RedesignId;
};

export function RedesignSwitcher({ active }: Props) {
  const { previous, next } = getRedesignCycle(active);
  return (
    <aside className="design-switcher" aria-label="Redesign switcher">
      <div>
        <p className="design-switcher-kicker">Prototype Lab</p>
        <h2 className="design-switcher-title">Choose a concept</h2>
      </div>
      <div className="design-switcher-grid">
        {REDESIGNS.map((item) => (
          <Link
            key={item.id}
            href={item.path}
            className={item.id === active ? "design-chip active" : "design-chip"}
          >
            {item.title}
          </Link>
        ))}
      </div>
      <div className="design-cycle-nav">
        <Link href={previous.path} className="design-cycle-link">
          Prev: {previous.title}
        </Link>
        <Link href={next.path} className="design-cycle-link">
          Next: {next.title}
        </Link>
      </div>
      <Link href="/redesigns" className="design-gallery-link">
        Back to gallery
      </Link>
    </aside>
  );
}
