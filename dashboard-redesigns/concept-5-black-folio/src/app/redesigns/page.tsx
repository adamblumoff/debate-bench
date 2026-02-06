import Link from "next/link";
import { REDESIGNS } from "@/app/redesigns/_lib/designs";

export default function RedesignGalleryPage() {
  return (
    <main className="redesign-gallery-page">
      <header className="redesign-gallery-hero">
        <p className="redesign-gallery-eyebrow">DebateBench Design Prototypes</p>
        <h1>Five UI redesign directions</h1>
        <p>
          These are static, non-functional wireframe implementations meant for visual direction
          picking only. Use the links below to open each prototype route.
        </p>
      </header>

      <section className="redesign-gallery-grid" aria-label="Redesign options">
        {REDESIGNS.map((item) => (
          <article key={item.id} className="redesign-gallery-card">
            <p className="redesign-gallery-tone">{item.tone}</p>
            <h2>{item.title}</h2>
            <p>{item.summary}</p>
            <Link href={item.path} className="redesign-gallery-link">
              Open prototype
            </Link>
          </article>
        ))}
      </section>
    </main>
  );
}
