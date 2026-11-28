// Every visible string of the energy extension, in one place (English keys of web/i18n/<lang>.json). Getters, so
// they read the catalogue when used. docs/ENERGY_PORT.md lists them for translators.
import { t } from "../../i18n.js";

export const TECH_LABEL = {
  get solar() { return t("Solar"); },
  get wind() { return t("Wind"); },
  get hydro() { return t("Hydro"); },
  get coal() { return t("Coal"); },
  get gas() { return t("Gas"); },
  get oil() { return t("Oil"); },
  get nuclear() { return t("Nuclear"); },
  get biomass() { return t("Biomass"); },
  get other() { return t("Other"); },
};

export const S = {
  get layer() { return t("Power plants by year"); },
  get layerHint() { return t("Plants appear in the year they started"); },
  get markers() { return t("Power plants"); },
  get markersHint() { return t("Operating power plants"); },
  get capacity() { return t("Capacity"); },
  get share() { return t("Share of generation"); },
  get gw() { return t("GW"); },
  title: (year) => t("Electricity in {year}", { year }),
  capIn: (year) => t("Capacity, {year}", { year }),
  shareIn: (year) => t("Generation, {year}", { year }),
  last12: (to) => t("Generation, 12 months to {month}", { month: to }),
  plants: (n) => t.plural(n, { one: "{n} plant", other: "{n} plants" }),
  mw: (mw) => t("{mw} MW", { mw }),
  since: (year) => t("Since {year}", { year }),
  until: (a, b) => t("{from} to {to}", { from: a, to: b }),
  get unnamed() { return t("Power plant"); },
};
