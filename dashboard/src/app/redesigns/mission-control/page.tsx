import { IBM_Plex_Mono, Sora } from "next/font/google";
import { RedesignSwitcher } from "@/app/redesigns/_components/RedesignSwitcher";
import styles from "./mission-control.module.css";

const display = Sora({ subsets: ["latin"], weight: ["600", "700", "800"] });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"] });

const kpi = [
  { label: "Top Model", value: "gpt-4.2", delta: "+42 Elo" },
  { label: "Judge Spread", value: "8.3%", delta: "low variance" },
  { label: "Side Bias", value: "1.8%", delta: "balanced" },
  { label: "Debates", value: "6,240", delta: "latest run" },
];

export default function MissionControlPage() {
  return (
    <main className={`${styles.page} ${display.className} ${mono.className}`}>
      <RedesignSwitcher active="mission-control" />
      <div className={styles.shell}>
        <aside className={styles.rail}>
          <p className={styles.railLabel}>Command Rail</p>
          <h1>Mission Control</h1>
          <p className={styles.railCopy}>Run-focused control layout with fixed operator context.</p>
          <div className={styles.railGroup}>
            <p>Run selector</p>
            <button>sample5-11-30-2025</button>
            <button>balanced-12-08-2025</button>
            <button>arena-01-14-2026</button>
          </div>
          <div className={styles.railGroup}>
            <p>Filters</p>
            <div className={styles.pills}>
              <span>Policy</span>
              <span>Science</span>
              <span>Economics</span>
              <span>gpt-4o</span>
              <span>claude-sonnet</span>
            </div>
          </div>
        </aside>

        <section className={styles.main}>
          <header className={styles.topbar}>
            <div>
              <p className={styles.eyebrow}>DebateBench Prototype</p>
              <h2>Operational Summary Deck</h2>
            </div>
            <div className={styles.actions}>
              <button>Refresh data</button>
              <button>Export JSONL</button>
            </div>
          </header>

          <section className={styles.kpiGrid}>
            {kpi.map((item) => (
              <article key={item.label} className={styles.kpiCard}>
                <p>{item.label}</p>
                <strong>{item.value}</strong>
                <span>{item.delta}</span>
              </article>
            ))}
          </section>

          <section className={styles.chartGrid}>
            <article className={styles.chartCard}>
              <header>
                <h3>Price to performance map</h3>
                <span>Elo mode</span>
              </header>
              <div className={styles.scatter} />
            </article>
            <article className={styles.chartCard}>
              <header>
                <h3>Head-to-head matrix</h3>
                <span>Win-rate heat</span>
              </header>
              <div className={styles.heatmap} />
            </article>
            <article className={styles.chartCard}>
              <header>
                <h3>Judge side preference</h3>
                <span>CV mean</span>
              </header>
              <div className={styles.bars}>
                <span style={{ width: "83%" }} />
                <span style={{ width: "68%" }} />
                <span style={{ width: "74%" }} />
                <span style={{ width: "58%" }} />
              </div>
            </article>
            <article className={styles.chartCard}>
              <header>
                <h3>Pricing table</h3>
                <span>Live snapshot</span>
              </header>
              <div className={styles.tableMock}>
                <div><span>gpt-4.2</span><span>$1.10 / $4.20</span></div>
                <div><span>claude-sonnet</span><span>$1.50 / $7.00</span></div>
                <div><span>gemini-2.5</span><span>$0.80 / $3.30</span></div>
              </div>
            </article>
          </section>
        </section>
      </div>
    </main>
  );
}
