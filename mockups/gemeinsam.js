// Nur für die Entwürfe: Kopf, Navigation und Wellenform je Fenster erzeugen, damit jedes Bild gleich aussieht.
const BEREICHE = [
  ["vertonen", "fa-wave-square", "Vertonen"],
  ["stimmen", "fa-user-group", "Stimmen"],
];
const APP = [
  ["auftraege", "fa-list-check", "Aufträge", "2"],
  ["protokoll", "fa-clock-rotate-left", "Protokoll"],
  ["einstellungen", "fa-sliders", "Einstellungen"],
];

function eintrag([k, s, t, z], aktiv) {
  return `<a class="nav-eintrag${k === aktiv ? " aktiv" : ""}"><i class="fa-solid ${s}"></i>${t}${z ? `<span class="zahl">${z}</span>` : ""}</a>`;
}

document.querySelectorAll("header.kopf[data-erzeugen]").forEach((kopf) => {
  kopf.innerHTML = `<div class="marke"><span class="symbol"><i class="fa-solid fa-volume-high"></i></span> Vertonung</div>
    <span class="rolle"><i class="fa-solid fa-wave-square"></i>macht aus Text Sprache</span>
    <div class="kopf-rechts">
      <span class="pille" title="Leitstelle http://192.168.1.20:8530"><span class="punkt"></span>Leitstelle</span>
      <span class="pille" title="Kellerwolke https://192.168.1.20:39280, Zweig Apps/Vertonung"><span class="punkt"></span>Kellerwolke</span>
      <span class="pille aktiv"><i class="fa-solid fa-gears"></i>1 läuft, 1 wartet</span>
      <button class="rund" title="Hilfe"><i class="fa-solid fa-circle-question"></i></button>
    </div>`;
});

document.querySelectorAll("nav.nav[data-aktiv]").forEach((nav) => {
  const aktiv = nav.dataset.aktiv;
  nav.innerHTML = `<div class="nav-gruppe">Vertonung</div>${BEREICHE.map((b) => eintrag(b, aktiv)).join("")}
    <div class="nav-gruppe">App</div>${APP.map((b) => eintrag(b, aktiv)).join("")}
    <div class="nav-fuss">
      <div class="konto"><span class="bild">C</span><span><div class="wer">chef</div><div class="wie">angemeldet mit Passwort</div></span><button class="rund" title="Abmelden"><i class="fa-solid fa-right-from-bracket"></i></button></div>
      <div class="fassung">Vertonung 0.1.0 · Appkern 0.21.1</div>
    </div>`;
});

// Wellenform: Säulen, gespielter Teil, Abspielkopf, Sprecherspur, Marker.
document.querySelectorAll(".welle[data-kopf]").forEach((welle) => {
  const kopf = Number(welle.dataset.kopf);
  const zahl = Number(welle.dataset.saeulen || 150);
  let saeulen = "";
  for (let i = 0; i < zahl; i++) {
    const h = 18 + 70 * Math.abs(Math.sin(i * 0.37) * Math.cos(i * 0.11 + 1.3)) + (i % 7) * 2;
    saeulen += `<span class="${i / zahl < kopf ? "gespielt" : ""}" style="height:${Math.min(100, h)}%"></span>`;
  }
  const spur = (welle.dataset.spur || "").split(" ").filter(Boolean).map((t) => {
    const [s, w] = t.split(":");
    return `<span style="flex:${w}; background:var(--${s})"></span>`;
  }).join("");
  const marker = (welle.dataset.marker || "").split(" ").filter(Boolean)
    .map((m) => `<i class="fa-solid fa-flag fahne" style="left:${Number(m) * 100}%"></i>`).join("");
  welle.innerHTML = `<div class="saeulen">${saeulen}</div><div class="sprecherspur">${spur}</div>${marker}<div class="abspielkopf" style="left:${kopf * 100}%"></div>`;
});

// Hell und dunkel umschalten (nur Entwurf).
const leiste = document.createElement("div");
leiste.className = "mock-leiste";
leiste.innerHTML = `<button data-t="hell" class="aktiv" title="Hell"><i class="fa-solid fa-sun"></i></button><button data-t="dunkel" title="Dunkel"><i class="fa-solid fa-moon"></i></button>`;
leiste.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  document.documentElement.dataset.theme = b.dataset.t;
  leiste.querySelectorAll("button").forEach((x) => x.classList.toggle("aktiv", x === b));
});
document.body.append(leiste);
if (location.hash === "#dunkel") leiste.querySelector('[data-t="dunkel"]').click();
