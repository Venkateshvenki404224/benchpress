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
        type: "links",
        heading: "Operator Track",
        links: [
          { urlPath: "/docs/operator" },
          { urlPath: "/docs/operator/prerequisites" },
          { urlPath: "/docs/operator/install" },
          { urlPath: "/docs/operator/wireguard-setup" },
          { urlPath: "/docs/operator/settings-reference" },
          { urlPath: "/docs/operator/database-server" },
          { urlPath: "/docs/operator/backup-and-restore" },
          { urlPath: "/docs/operator/golden-images" },
          { urlPath: "/docs/operator/image-cache" },
          { urlPath: "/docs/operator/users-and-roles" },
          { urlPath: "/docs/operator/upgrading" },
          { urlPath: "/docs/operator/production-safety" },
          { urlPath: "/docs/operator/diagnostics" },
          { urlPath: "/docs/operator/credits-and-billing" },
          { urlPath: "/docs/operator/admission-and-limits" },
          { urlPath: "/docs/operator/hosted-signup" },
        ],
      },
      {
        type: "links",
        heading: "Reference Track",
        links: [
          { urlPath: "/docs/reference" },
          { urlPath: "/docs/reference/architecture" },
          { urlPath: "/docs/reference/data-model" },
          { urlPath: "/docs/reference/api" },
          { urlPath: "/docs/reference/deploy-pipeline" },
          { urlPath: "/docs/reference/lifecycle-and-events" },
          { urlPath: "/docs/reference/networking" },
          { urlPath: "/docs/reference/realtime" },
          { urlPath: "/docs/reference/configuration" },
          { urlPath: "/docs/reference/cli-and-scripts" },
          { urlPath: "/docs/reference/glossary" },
        ],
      },
      // The routing table an agent actually reads. Tasks first, because an agent
      // arrives with a task and not with a track. Every line names exactly one
      // page, so there is nothing to choose between.
      {
        type: "markdown",
        heading: "Agent Guidance",
        body: [
          "Three tracks. Read `user/` for working inside a deployed bench, `operator/` for",
          "running the host, and `reference/` for the data model, the API and the internals.",
          "",
          "Route by the task, not by the track:",
          "",
          "- Connect over SSH, or find the SSH password -> `/docs/user/connect-ssh-vpn`",
          "- Get a bench running from a template -> `/docs/user/deploy-from-template`",
          "- Open the bench site in a browser -> `/docs/user/open-your-site`",
          "- Put a laptop or phone on the VPN -> `/docs/user/vpn-devices`",
          "- Open the browser VS Code session -> `/docs/user/code-server`",
          "- A bench stopped, or a countdown ran out -> `/docs/user/leases-and-credits`",
          "- Any user-facing symptom, with its cause -> `/docs/user/troubleshooting`",
          "- Install BenchPress on a new host -> `/docs/operator/install`",
          "- Stand up WireGuard -> `/docs/operator/wireguard-setup`",
          "- Find a setting, its default and where it is edited -> `/docs/operator/settings-reference`",
          "- Back up or restore a bench site -> `/docs/operator/backup-and-restore`",
          "- Make deploys faster -> `/docs/operator/golden-images`",
          "- Diagnose a host that is misbehaving -> `/docs/operator/diagnostics`",
          "- Turn on metering, caps or signup -> `/docs/operator/credits-and-billing`",
          "- Look up a DocType, a field or a permission rule -> `/docs/reference/data-model`",
          "- Call an endpoint, or check what it verifies -> `/docs/reference/api`",
          "- Understand what a deploy does, step by step -> `/docs/reference/deploy-pipeline`",
          "- Find what changes a row with no user action -> `/docs/reference/lifecycle-and-events`",
          "- Work out which address a bench answers on -> `/docs/reference/networking`",
          "- Subscribe to live deploy output -> `/docs/reference/realtime`",
          "- Decide whether a change needs a rebuild -> `/docs/reference/configuration`",
          "- Run something from a shell -> `/docs/reference/cli-and-scripts`",
          "- Check what a word means here -> `/docs/reference/glossary`",
          "",
          "Two facts that prevent wrong answers. Devices are `VPN Peer` records in the",
          "`vpn_management` app, so there is no Device DocType. Credits are off by default,",
          "so `enable_credits` is `0` and no page about billing applies to a plain install.",
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
    {
      title: "Operator",
      base: "operator",
      children: [
        { title: "Start", pages: ["index"] },
        {
          title: "Stand a host up",
          pages: ["prerequisites", "install", "wireguard-setup"],
        },
        {
          title: "Run it",
          pages: [
            "settings-reference",
            "database-server",
            "backup-and-restore",
            "users-and-roles",
          ],
        },
        {
          title: "Images and speed",
          pages: ["golden-images", "image-cache"],
        },
        {
          title: "Keep it safe",
          pages: ["upgrading", "production-safety", "diagnostics"],
        },
        {
          title: "Optional — running it for a team",
          pages: [
            "credits-and-billing",
            "admission-and-limits",
            "hosted-signup",
          ],
        },
      ],
    },
    {
      title: "Reference",
      base: "reference",
      children: [
        { title: "Start", pages: ["index"] },
        {
          title: "What it is made of",
          pages: ["architecture", "data-model", "api"],
        },
        {
          title: "What it does at runtime",
          pages: [
            "deploy-pipeline",
            "lifecycle-and-events",
            "networking",
            "realtime",
          ],
        },
        {
          title: "Driving it yourself",
          pages: ["configuration", "cli-and-scripts"],
        },
        { title: "Words", pages: ["glossary"] },
      ],
    },
  ],
});
