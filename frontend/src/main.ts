import "appkern-oberflaeche/stil.css";
import "./stil/vertonung.css";
import { aufnahmeEinrichten } from "appkern-oberflaeche";
import { mount } from "svelte";
import App from "./App.svelte";

// Proben aufnehmen im Browser: eigener Gerätespeicher, ohne Live-Mitschrift
aufnahmeEinrichten({ app: "vertonung", hoeren: null, name: "Probe" });

mount(App, { target: document.getElementById("app")! });
