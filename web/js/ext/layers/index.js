// Map-art extension: expressways, national highways, railways, seaports and airports, each as a static layer drawn
// into the cached map (nothing animates; an idle map draws no frames), with a switch in the "Map" menu.
//
// Data: infrastructure.json (loaded eagerly by main.js right after the first frame; app.loadData returns the same
// promise). A missing file (null) leaves its layers off and their switches harmless.
import { createModel } from "./model.js";
import { makeLayers } from "./layers.js";
import { tips } from "./tips.js";
import { t } from "../../i18n.js";

const TOGGLES = [
  { id: "roads", label: t("Roads"), icon: "t-road", def: true, title: t("Expressways and national highways"), layers: ["roads"] },
  { id: "rail", label: t("Railways"), icon: "t-rail", def: true, title: t("Railway lines"), layers: ["rail"] },
  { id: "hubs", label: t("Ports & airports"), icon: "d-harbor", def: true, title: t("Seaports and passenger airports"), layers: ["hubs"] },
];

export function install(app) {
  const model = createModel(app.w);
  const on = Object.fromEntries(TOGGLES.map((tg) => [tg.id, tg.def]));
  const layers = makeLayers(model, on, { tips, app });
  for (const l of layers) app.registerStaticLayer(l);

  for (const tg of TOGGLES) {
    app.ui.addMapToggle({
      id: tg.id, label: tg.label, icon: tg.icon, title: tg.title, default: tg.def, menu: tg.menu,
      get: () => on[tg.id],
      set: (v) => {
        on[tg.id] = !!v;
        app.requestDraw();
      },
    });
  }

  const apply = (name, data) => {
    model.setData(name, data);
    app.requestDraw();
  };
  for (const name of ["infrastructure"]) {
    if (app.data[name] !== undefined) apply(name, app.data[name]);
    else app.loadData(name).then((d) => apply(name, d), (err) => console.warn(`map layers: ${name} failed to load`, err));
  }

  // For debugging and the gallery: the model and switches.
  app.mapArt = { model, on, layers };
}
