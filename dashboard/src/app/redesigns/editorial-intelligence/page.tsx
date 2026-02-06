import { DM_Mono, Fraunces, Source_Sans_3 } from "next/font/google";
import { RedesignSwitcher } from "@/app/redesigns/_components/RedesignSwitcher";
import styles from "./editorial-intelligence.module.css";

const display = Fraunces({ subsets: ["latin"], weight: ["500", "600", "700"] });
const body = Source_Sans_3({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });
const mono = DM_Mono({ subsets: ["latin"], weight: ["400", "500"] });

export default function EditorialIntelligencePage() {
  return (
    <main className={`${styles.page} ${display.className} ${body.className} ${mono.className}`}>
      <RedesignSwitcher active="editorial-intelligence" />

      <div className={styles.shell}>
        <header className={styles.masthead}>
          <p className={styles.issue}>Issue 07 / Data Review Edition</p>
          <h1>Editorial Intelligence</h1>
          <p className={styles.deck}>
            A report-like wireframe that presents debate results as a curated story rather than
            a control console.
          </p>
        </header>

        <div className={styles.layout}>
          <aside className={styles.sidebar}>
            <section>
              <p className={styles.sectionKicker}>Current run</p>
              <h2>sample5-11-30-2025</h2>
              <p>38 models · 6,240 debates</p>
            </section>

            <section>
              <p className={styles.sectionKicker}>Filters</p>
              <div className={styles.filterList}>
                <span>Policy</span>
                <span>Science</span>
                <span>Economics</span>
                <span>gpt-4.2</span>
                <span>claude-sonnet</span>
              </div>
            </section>

            <section className={styles.portraitCard}>
              <p className={styles.sectionKicker}>Lead signal</p>
              <strong>gpt-4.2</strong>
              <p>Maintains first place in Elo and holds cost efficiency under $1.20 input.</p>
            </section>
          </aside>

          <section className={styles.story}>
            <article className={styles.storyBlock}>
              <header>
                <p className={styles.sectionKicker}>Section A</p>
                <h3>Performance overview</h3>
              </header>
              <div className={styles.twoCol}>
                <div className={styles.chartPlate}>
                  <p>Price to performance scatter</p>
                  <div className={styles.scatterMock} />
                </div>
                <div className={styles.noteCard}>
                  <p>
                    Efficiency leaders cluster tightly, suggesting pricing pressure converges around
                    similar quality tiers in this run configuration.
                  </p>
                </div>
              </div>
            </article>

            <article className={styles.storyBlock}>
              <header>
                <p className={styles.sectionKicker}>Section B</p>
                <h3>Model and topic structure</h3>
              </header>
              <div className={styles.threeCol}>
                <div className={styles.chartPlate}>
                  <p>Head-to-head grid</p>
                  <div className={styles.heatMock} />
                </div>
                <div className={styles.chartPlate}>
                  <p>Dimension score lattice</p>
                  <div className={styles.barsMock}>
                    <span style={{ width: "82%" }} />
                    <span style={{ width: "65%" }} />
                    <span style={{ width: "74%" }} />
                    <span style={{ width: "57%" }} />
                  </div>
                </div>
                <div className={styles.chartPlate}>
                  <p>Cost table snapshot</p>
                  <div className={styles.tableMock}>
                    <div><span>gpt-4.2</span><span>$1.10 / $4.20</span></div>
                    <div><span>claude-sonnet</span><span>$1.50 / $7.00</span></div>
                    <div><span>gemini-2.5</span><span>$0.80 / $3.30</span></div>
                  </div>
                </div>
              </div>
            </article>
          </section>
        </div>
      </div>
    </main>
  );
}
