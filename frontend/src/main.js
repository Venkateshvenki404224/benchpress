import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import { startServerClock } from "./serverClock";
import { initSocket } from "./socket";

import {
	Alert,
	Badge,
	Button,
	Dialog,
	ErrorMessage,
	FormControl,
	Input,
	TextInput,
	frappeRequest,
	pageMetaPlugin,
	resourcesPlugin,
	setConfig,
} from "frappe-ui";

import "./index.css";

const globalComponents = {
	Button,
	TextInput,
	Input,
	FormControl,
	ErrorMessage,
	Dialog,
	Alert,
	Badge,
};

const app = createApp(App);

setConfig("resourceFetcher", frappeRequest);
// Datetimes are stored in the site's timezone; dayjsLocal needs it to render
// relative times against the viewer's clock.
setConfig("systemTimezone", window.system_timezone);

app.use(router);
app.use(resourcesPlugin);
app.use(pageMetaPlugin);

const socket = initSocket();
app.config.globalProperties.$socket = socket;

// Before the first countdown renders: a browser clock minutes out either ends a
// lease early on screen or keeps showing time that is already gone.
startServerClock();

for (const key in globalComponents) {
	app.component(key, globalComponents[key]);
}

app.mount("#app");
