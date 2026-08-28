import { defineDocsConfig } from "leadtype";

export default defineDocsConfig({
  product: {
    name: "BenchPress",
    tagline: "Press a button. Get a Frappe bench.",
  },
  llms: {
    sections: [
      {
        type: "markdown",
        heading: "Overview",
        body: [
          "BenchPress deploys a Frappe bench from a template. An operator describes a lab",
          "once — a Frappe version and a list of apps — and anyone with access deploys it,",
          "works in it over SSH or a browser VS Code session, and destroys it when the task",
          "is done.",
          "",
          "- Self-hosted. One box, Docker, no external control plane.",
          "- Every bench reachable only over WireGuard.",
          "- Built on the Frappe framework, with a Vue 3 single-page app on the front.",
        ].join("\n"),
      },
      {
        type: "links",
        heading: "Best Starting Points",
        links: [
          { urlPath: "/docs/user/quick-tour" },
          { urlPath: "/docs/user/deploy-from-template" },
        ],
      },
      // Every page, with its own description, because llms.txt is the routing
      // table an HTTP agent reads. A page missing from here is a page it has
      // to find by crawling.
      {
        type: "links",
        heading: "User Track",
        links: [
          { urlPath: "/docs" },
          { urlPath: "/docs/user/quick-tour" },
          { urlPath: "/docs/user/deploy-from-template" },
          { urlPath: "/docs/user/create-a-lab" },
          { urlPath: "/docs/user/lab-detail" },
          { urlPath: "/docs/user/lifecycle" },
          { urlPath: "/docs/user/vpn-devices" },
          { urlPath: "/docs/user/open-your-site" },
          { urlPath: "/docs/user/connect-ssh-vpn" },
          { urlPath: "/docs/user/code-server" },
          { urlPath: "/docs/user/logs-and-monitoring" },
          { urlPath: "/docs/user/leases-and-credits" },
          { urlPath: "/docs/user/troubleshooting" },
        ],
      },
      {
        type: "markdown",
        heading: "Agent Guidance",
        body: [
          "Three tracks. Read `user/` for working inside a deployed bench, `operator/` for",
          "running the host, and `reference/` for the data model and the HTTP API. Start",
          "from the quick tour when you do not yet know which screen owns a task.",
        ].join("\n"),
      },
    ],
  },
  // Authored pages are .mdx. Every .md under docs/ is a legacy guide that keeps
  // working until the page replacing it lands, so lint skips them. Setting
  // `ignore` replaces leadtype's defaults, so they are restated here.
  lint: {
    ignore: [
      "**/node_modules/**",
      "**/shared/**",
      "**/_shared/**",
      "**/_partials/**",
      "**/*.md",
    ],
  },
  // A navigation entry naming a page that does not exist is a config-link
  // error, so a track stays empty until its first page lands.
  navigation: [
    {
      title: "User",
      base: "user",
      children: [
        { title: "Start", pages: ["quick-tour"] },
        {
          title: "Get a bench running",
          pages: [
            "deploy-from-template",
            "create-a-lab",
            "lab-detail",
            "lifecycle",
          ],
        },
        {
          title: "Get into the bench",
          pages: [
            "vpn-devices",
            "open-your-site",
            "connect-ssh-vpn",
            "code-server",
          ],
        },
        {
          title: "Watch it and pay for it",
          pages: ["logs-and-monitoring", "leases-and-credits"],
        },
        { title: "When it goes wrong", pages: ["troubleshooting"] },
      ],
    },
    { title: "Operator", base: "operator", children: [] },
    { title: "Reference", base: "reference", children: [] },
  ],
});
