import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";

import "./style.css";
import "./assets/github-theme.css";

const app = createApp(App);

app.config.errorHandler = (err) => {
  console.error("Vue Error:", err);
};

app.use(router);
app.mount("#app");
