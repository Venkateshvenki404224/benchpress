import {
	D as e,
	G as t,
	S as n,
	a as r,
	b as i,
	c as a,
	g as o,
	m as s,
	n as c,
	o as l,
	q as u,
	s as d,
	t as f,
	u as p,
	v as m,
	w as h,
} from "./asyncToGenerator-xMs8Wj7k.js";
import { a as g } from "./index-ifQeZ2Ak.js";
import { t as _ } from "./GlassCard--GH8BpzT.js";
var v = { class: `animate-fade-up` },
	y = { key: 0, class: `text-bp-muted text-center py-12` },
	b = { key: 1, class: `text-center py-12` },
	x = { key: 2, class: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4` },
	S = { class: `flex items-start justify-between mb-4` },
	C = { class: `text-lg font-semibold text-bp-text` },
	w = { class: `text-bp-muted text-sm` },
	T = { class: `flex items-center gap-4 text-sm text-bp-dim mb-4` },
	E = { class: `flex gap-2` },
	D = [`onClick`, `disabled`],
	O = {
		__name: `LabsPage`,
		setup(O) {
			let k = s(`$call`),
				A = e([]),
				j = e(!0);
			function M() {
				return N.apply(this, arguments);
			}
			function N() {
				return (
					(N = f(function* () {
						j.value = !0;
						try {
							A.value = yield k(`benchpress.api.get_labs`);
						} catch (e) {
							console.error(`Failed to fetch labs:`, e);
						}
						j.value = !1;
					})),
					N.apply(this, arguments)
				);
			}
			function P(e) {
				return F.apply(this, arguments);
			}
			function F() {
				return (
					(F = f(function* (e) {
						try {
							yield k(`benchpress.api.build_lab_image`, { lab_name: e }), yield M();
						} catch (e) {
							console.error(`Build failed:`, e);
						}
					})),
					F.apply(this, arguments)
				);
			}
			function I(e) {
				let t = {
					Ready: `bg-bp-green/10 text-bp-green`,
					Building: `bg-bp-amber/10 text-bp-amber`,
					Draft: `bg-white/5 text-bp-muted`,
					Error: `bg-bp-red/10 text-bp-red`,
				};
				return t[e] || t.Draft;
			}
			return (
				o(M),
				(e, o) => {
					let s = n(`router-link`);
					return (
						m(),
						a(`div`, v, [
							o[2] ||
								(o[2] = r(
									`div`,
									{ class: `flex items-center justify-between mb-8` },
									[
										r(`div`, null, [
											r(
												`h1`,
												{ class: `text-2xl font-bold text-bp-text` },
												`Labs`
											),
											r(
												`p`,
												{ class: `text-bp-muted text-sm mt-1` },
												`Pre-configured bench templates ready to deploy`
											),
										]),
										r(
											`a`,
											{ href: `/app/lab/new`, class: `btn-primary` },
											`+ New Lab`
										),
									],
									-1
								)),
							j.value
								? (m(), a(`div`, y, `Loading labs...`))
								: A.value.length === 0
								? (m(),
								  a(`div`, b, [
										...(o[0] ||
											(o[0] = [
												r(
													`p`,
													{ class: `text-bp-muted mb-4` },
													`No labs created yet`,
													-1
												),
												r(
													`a`,
													{ href: `/app/lab/new`, class: `btn-primary` },
													`Create your first lab`,
													-1
												),
											])),
								  ]))
								: (m(),
								  a(`div`, x, [
										(m(!0),
										a(
											c,
											null,
											i(
												A.value,
												(e) => (
													m(),
													l(
														_,
														{
															key: e.name,
															shimmer: e.status === `Ready`,
															class: `cursor-pointer hover:-translate-y-0.5 transition-transform`,
														},
														{
															default: h(() => {
																var n;
																return [
																	r(`div`, S, [
																		r(`div`, null, [
																			r(
																				`h3`,
																				C,
																				u(
																					e.title ||
																						e.lab_id
																				),
																				1
																			),
																			r(
																				`p`,
																				w,
																				u(
																					e.frappe_version
																				),
																				1
																			),
																		]),
																		r(
																			`span`,
																			{
																				class: t([
																					`px-2 py-0.5 rounded text-xs font-medium`,
																					I(e.status),
																				]),
																			},
																			u(e.status),
																			3
																		),
																	]),
																	r(`div`, T, [
																		r(
																			`span`,
																			null,
																			u(
																				((n = e.apps) ==
																				null
																					? void 0
																					: n.length) ||
																					0
																			) + ` apps`,
																			1
																		),
																		r(
																			`span`,
																			null,
																			u(
																				e.memory_limit ||
																					`512m`
																			) + ` RAM`,
																			1
																		),
																		r(
																			`span`,
																			null,
																			u(e.cpu_cores || 1) +
																				` CPU`,
																			1
																		),
																	]),
																	r(`div`, E, [
																		e.status === `Ready`
																			? (m(),
																			  l(
																					s,
																					{
																						key: 0,
																						to: `/dashboard/deploy/${e.name}`,
																						class: `btn-primary text-xs`,
																					},
																					{
																						default: h(
																							() => [
																								...(o[1] ||
																									(o[1] =
																										[
																											p(
																												` Deploy `,
																												-1
																											),
																										])),
																							]
																						),
																						_: 1,
																					},
																					8,
																					[`to`]
																			  ))
																			: d(``, !0),
																		r(
																			`button`,
																			{
																				onClick: g(
																					(t) =>
																						P(e.name),
																					[`stop`]
																				),
																				class: `btn-secondary text-xs`,
																				disabled:
																					e.status ===
																					`Building`,
																			},
																			u(
																				e.status ===
																					`Building`
																					? `Building...`
																					: `Build Image`
																			),
																			9,
																			D
																		),
																	]),
																];
															}),
															_: 2,
														},
														1032,
														[`shimmer`]
													)
												)
											),
											128
										)),
								  ])),
						])
					);
				}
			);
		},
	};
export { O as default };
