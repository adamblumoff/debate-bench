"use client";

const tiles = [
  { title: "Fastest small models", desc: "Low-token, high win-rate picks", href: "#highlights" },
  { title: "Best price for chat", desc: "Price-per-million vs quality", href: "#pricing" },
  { title: "Multimodal leaders", desc: "By category performance", href: "#topics" },
  { title: "Long-context champs", desc: "Side bias & stability", href: "#judges" },
];

export function DiscoveryTiles() {
  return (
    <div className="grid gap-3 md:grid-cols-4">
      {tiles.map((t) => (
        <a key={t.title} href={t.href} className="tile">
          <p className="text-sm font-semibold text-white">{t.title}</p>
          <p className="text-xs text-slate-400">{t.desc}</p>
        </a>
      ))}
    </div>
  );
}
