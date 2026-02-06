import { JetBrains_Mono, Manrope } from "next/font/google";
import { RedesignSwitcher } from "@/app/redesigns/_components/RedesignSwitcher";
import styles from "./financial-terminal.module.css";

const display = Manrope({ subsets: ["latin"], weight: ["500", "600", "700", "800"] });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500", "700"] });

const strips = [
  "gpt-4.2 +1.4%",
  "claude-sonnet -0.6%",
  "gemini-2.5 +2.1%",
  "deepseek-r1 +0.3%",
  "qwen-max -1.2%",
];

const miniRows = [
  ["Total debates", "6,240"],
  ["Models", "38"],
  ["Avg tokens", "15.1k"],
  ["Judge agreement", "82.4%"],
  ["Median cost", "$0.84"],
  ["Bias spread", "1.9%"],
] as const;

export default function FinancialTerminalPage() {
  return (
    <main className={`${styles.page} ${display.className} ${mono.className}`}>
      <RedesignSwitcher active="financial-terminal" />
      <div className={styles.shell}>
        <header className={styles.header}>
          <div>
            <p className={styles.kicker}>DebateBench Wireframe</p>
            <h1>Financial Terminal</h1>
          </div>
          <div className={styles.headerActions}>
            <button>Run: sample5</button>
            <button>Category basket</button>
            <button>Export snapshot</button>
          </div>
        </header>

        <section className={styles.ticker} aria-label="Signal strip">
          {strips.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </section>

        <section className={styles.grid}>
          <aside className={styles.sidePanel}>
            <h2>Signal board</h2>
            <div className={styles.signalGrid}>
              {miniRows.map(([label, value]) => (
                <div key={label} className={styles.signalCell}>
                  <p>{label}</p>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>

            <div className={styles.orderBook}>
              <h3>Model stack</h3>
              <div>
                <span>gpt-4.2</span>
                <span>+42 Elo</span>
              </div>
              <div>
                <span>claude-sonnet</span>
                <span>+36 Elo</span>
              </div>
              <div>
                <span>gemini-2.5</span>
                <span>+27 Elo</span>
              </div>
              <div>
                <span>qwen-max</span>
                <span>+22 Elo</span>
              </div>
            </div>
          </aside>

          <section className={styles.mainPanel}>
            <article className={styles.panel}>
              <header>
                <h3>Price to Elo map</h3>
                <span>Quadrant mock</span>
              </header>
              <div className={styles.scatterMock} />
            </article>

            <article className={styles.panel}>
              <header>
                <h3>Head-to-head heatbook</h3>
                <span>Matrix mock</span>
              </header>
              <div className={styles.heatMock} />
            </article>

            <article className={styles.panel}>
              <header>
                <h3>Judge side preference tape</h3>
                <span>CV adjusted</span>
              </header>
              <div className={styles.tape}>
                <span style={{ width: "84%" }} />
                <span style={{ width: "72%" }} />
                <span style={{ width: "67%" }} />
                <span style={{ width: "58%" }} />
                <span style={{ width: "77%" }} />
              </div>
            </article>

            <article className={styles.panel}>
              <header>
                <h3>Cost ladder table</h3>
                <span>USD / 1M</span>
              </header>
              <div className={styles.tableMock}>
                <div><span>gpt-4.2</span><span>$1.10</span><span>$4.20</span></div>
                <div><span>claude-sonnet</span><span>$1.50</span><span>$7.00</span></div>
                <div><span>gemini-2.5</span><span>$0.80</span><span>$3.30</span></div>
                <div><span>qwen-max</span><span>$0.70</span><span>$2.90</span></div>
              </div>
            </article>
          </section>
        </section>
      </div>
    </main>
  );
}
