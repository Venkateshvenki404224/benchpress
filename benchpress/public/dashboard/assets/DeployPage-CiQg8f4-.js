import {
	A as e,
	C as t,
	D as n,
	G as r,
	S as i,
	_ as a,
	a as o,
	b as s,
	c,
	d as l,
	g as u,
	h as d,
	m as f,
	n as p,
	o as m,
	q as h,
	s as g,
	t as _,
	u as v,
	v as y,
	w as b,
} from "./asyncToGenerator-xMs8Wj7k.js";
import { t as x } from "./index-ifQeZ2Ak.js";
import { t as S } from "./GlassCard--GH8BpzT.js";
import { t as C } from "./StatusDot-NHL9V5FS.js";
var w = { key: 0, class: `text-bp-dim mr-2` },
	T = { key: 0, class: `text-bp-dim` },
	E = {
		__name: `Terminal`,
		props: { lines: { type: Array, default: () => [] } },
		setup(e) {
			let i = e,
				a = n(null);
			function l(e) {
				return e ? new Date(e).toLocaleTimeString() : ``;
			}
			return (
				t(
					() => i.lines.length,
					_(function* () {
						yield d(), a.value && (a.value.scrollTop = a.value.scrollHeight);
					})
				),
				(t, n) => (
					y(),
					c(
						`div`,
						{ ref_key: `termRef`, ref: a, class: `terminal` },
						[
							(y(!0),
							c(
								p,
								null,
								s(
									e.lines,
									(e, t) => (
										y(),
										c(
											`div`,
											{
												key: t,
												class: r([
													`terminal-line`,
													`terminal-line-${e.type || `info`}`,
												]),
											},
											[
												e.timestamp
													? (y(),
													  c(
															`span`,
															w,
															`[` + h(l(e.timestamp)) + `]`,
															1
													  ))
													: g(``, !0),
												o(`span`, null, h(e.message), 1),
											],
											2
										)
									)
								),
								128
							)),
							e.lines.length === 0
								? (y(), c(`div`, T, `Waiting for logs...`))
								: g(``, !0),
						],
						512
					)
				)
			);
		},
	},
	D = { class: `animate-fade-up max-w-3xl mx-auto` },
	O = { key: 0, class: `text-bp-muted text-sm mb-8` },
	k = { class: `text-bp-green` },
	A = { class: `space-y-4` },
	j = { class: `text-bp-text` },
	M = { key: 0 },
	N = { class: `flex flex-wrap gap-2` },
	P = [`disabled`],
	F = { key: 2 },
	I = { class: `flex items-center gap-3 mb-4` },
	L = { class: `font-medium text-bp-text` },
	R = { key: 0, class: `flex gap-3` },
	z = {
		__name: `DeployPage`,
		setup(t) {
			let r = f(`$call`),
				d = f(`$socket`),
				w = x().params.lab,
				T = n(null),
				z = n(!1),
				B = n(!1),
				V = n(!1),
				H = n(``),
				U = n([]);
			function W() {
				return G.apply(this, arguments);
			}
			function G() {
				return (
					(G = _(function* () {
						try {
							T.value = yield r(`benchpress.api.get_lab`, { lab_name: w });
						} catch (e) {
							console.error(`Failed to fetch lab:`, e);
						}
					})),
					G.apply(this, arguments)
				);
			}
			function K() {
				return q.apply(this, arguments);
			}
			function q() {
				return (
					(q = _(function* () {
						(z.value = !0),
							(U.value = [
								{
									message: `Starting deployment...`,
									type: `info`,
									timestamp: new Date().toISOString(),
								},
							]);
						try {
							let e = yield r(`benchpress.api.create_bench`, { lab_name: w });
							H.value =
								(e == null ? void 0 : e.bench_name) ||
								(e == null ? void 0 : e.name) ||
								``;
						} catch (e) {
							U.value.push({ message: `Error: ${e.message || e}`, type: `error` }),
								(V.value = !0),
								(B.value = !0);
						}
					})),
					q.apply(this, arguments)
				);
			}
			function J(e) {
				(e.bench === H.value || !H.value) &&
					(U.value.push({
						message: e.log || e.message,
						type: e.type || e.log_type || `info`,
						timestamp: e.timestamp,
					}),
					(e.type === `success` || e.log_type === `success`) && (B.value = !0),
					(e.type === `error` || e.log_type === `error`) &&
						((V.value = !0), (B.value = !0)));
			}
			return (
				u(() => {
					W(), d.on(`bench_deploy_log`, J);
				}),
				a(() => {
					d.off(`bench_deploy_log`, J);
				}),
				(t, n) => {
					let r = i(`router-link`);
					return (
						y(),
						c(`div`, D, [
							l(
								r,
								{
									to: `/dashboard`,
									class: `text-bp-muted hover:text-bp-text text-sm mb-6 inline-flex items-center gap-1`,
								},
								{
									default: b(() => [
										...(n[0] || (n[0] = [v(` ← Back to Labs `, -1)])),
									]),
									_: 1,
								}
							),
							n[6] ||
								(n[6] = o(
									`h1`,
									{ class: `text-2xl font-bold text-bp-text mb-2` },
									`Deploy Bench`,
									-1
								)),
							T.value
								? (y(),
								  c(`p`, O, [
										n[1] || (n[1] = v(`From `, -1)),
										o(`span`, k, h(T.value.title || T.value.lab_id), 1),
										v(` · ` + h(T.value.frappe_version), 1),
								  ]))
								: g(``, !0),
							!z.value && !B.value
								? (y(),
								  m(
										S,
										{ key: 1, class: `mb-6` },
										{
											default: b(() => {
												var t, r;
												return [
													o(`div`, A, [
														o(`div`, null, [
															n[2] ||
																(n[2] = o(
																	`label`,
																	{
																		class: `text-sm text-bp-muted mb-1 block`,
																	},
																	`Lab`,
																	-1
																)),
															o(
																`div`,
																j,
																h(
																	((t = T.value) == null
																		? void 0
																		: t.title) || e(w)
																),
																1
															),
														]),
														!(
															(r = T.value) == null ||
															(r = r.apps) == null
														) && r.length
															? (y(),
															  c(`div`, M, [
																	n[3] ||
																		(n[3] = o(
																			`label`,
																			{
																				class: `text-sm text-bp-muted mb-1 block`,
																			},
																			`Apps to install`,
																			-1
																		)),
																	o(`div`, N, [
																		(y(!0),
																		c(
																			p,
																			null,
																			s(
																				T.value.apps,
																				(e) => (
																					y(),
																					c(
																						`span`,
																						{
																							key: e.app_name,
																							class: `px-2 py-1 rounded text-xs bg-white/5 text-bp-muted`,
																						},
																						h(
																							e.app_name
																						),
																						1
																					)
																				)
																			),
																			128
																		)),
																	]),
															  ]))
															: g(``, !0),
														o(
															`button`,
															{
																onClick: K,
																class: `btn-primary w-full py-3 text-center`,
																disabled: !T.value,
															},
															` Deploy Bench `,
															8,
															P
														),
													]),
												];
											}),
											_: 1,
										}
								  ))
								: g(``, !0),
							z.value || B.value
								? (y(),
								  c(`div`, F, [
										l(
											S,
											{ class: `mb-4` },
											{
												default: b(() => [
													o(`div`, I, [
														l(
															C,
															{
																status: B.value
																	? V.value
																		? `error`
																		: `running`
																	: `deploying`,
															},
															null,
															8,
															[`status`]
														),
														o(
															`span`,
															L,
															h(
																B.value
																	? V.value
																		? `Deploy Failed`
																		: `Deploy Complete`
																	: `Deploying...`
															),
															1
														),
													]),
													l(E, { lines: U.value }, null, 8, [`lines`]),
												]),
												_: 1,
											}
										),
										B.value && !V.value
											? (y(),
											  c(`div`, R, [
													l(
														r,
														{
															to: `/dashboard/benches`,
															class: `btn-primary`,
														},
														{
															default: b(() => [
																...(n[4] ||
																	(n[4] = [
																		v(`View Benches`, -1),
																	])),
															]),
															_: 1,
														}
													),
													H.value
														? (y(),
														  m(
																r,
																{
																	key: 0,
																	to: `/dashboard/bench/${H.value}`,
																	class: `btn-secondary`,
																},
																{
																	default: b(() => [
																		...(n[5] ||
																			(n[5] = [
																				v(
																					`Bench Detail`,
																					-1
																				),
																			])),
																	]),
																	_: 1,
																},
																8,
																[`to`]
														  ))
														: g(``, !0),
											  ]))
											: g(``, !0),
								  ]))
								: g(``, !0),
						])
					);
				}
			);
		},
	};
export { z as default };
