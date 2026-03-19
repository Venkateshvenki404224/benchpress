const __vite__mapDeps = (
	i,
	m = __vite__mapDeps,
	d = m.f ||
		(m.f = [
			"assets/LabsPage-seyMQP8C.js",
			"assets/asyncToGenerator-xMs8Wj7k.js",
			"assets/GlassCard--GH8BpzT.js",
			"assets/BenchListPage-DweME6wd.js",
			"assets/StatBar-BG9jHiRY.js",
			"assets/StatusDot-NHL9V5FS.js",
			"assets/DeployPage-CiQg8f4-.js",
			"assets/BenchDetailPage-C45h6avy.js",
			"assets/Login-hP39zToz.js",
		])
) => i.map((i) => d[i]);
import {
	A as e,
	B as t,
	C as n,
	D as r,
	E as i,
	F as a,
	G as o,
	H as s,
	I as c,
	L as l,
	M as u,
	N as d,
	O as f,
	P as ee,
	R as te,
	S as ne,
	U as re,
	V as ie,
	W as ae,
	a as p,
	c as m,
	d as h,
	f as oe,
	h as se,
	i as g,
	j as _,
	k as ce,
	l as v,
	m as y,
	p as b,
	q as le,
	r as ue,
	s as de,
	t as x,
	u as fe,
	v as S,
	w as pe,
	y as C,
	z as me,
} from "./asyncToGenerator-xMs8Wj7k.js";
var he = Object.defineProperty,
	ge = (e, t) => {
		let n = {};
		for (var r in e) he(n, r, { get: e[r], enumerable: !0 });
		return t || he(n, Symbol.toStringTag, { value: `Module` }), n;
	};
(function () {
	let e = document.createElement(`link`).relList;
	if (e && e.supports && e.supports(`modulepreload`)) return;
	for (let e of document.querySelectorAll(`link[rel="modulepreload"]`)) n(e);
	new MutationObserver((e) => {
		for (let t of e)
			if (t.type === `childList`)
				for (let e of t.addedNodes)
					e.tagName === `LINK` && e.rel === `modulepreload` && n(e);
	}).observe(document, { childList: !0, subtree: !0 });
	function t(e) {
		let t = {};
		return (
			e.integrity && (t.integrity = e.integrity),
			e.referrerPolicy && (t.referrerPolicy = e.referrerPolicy),
			e.crossOrigin === `use-credentials`
				? (t.credentials = `include`)
				: e.crossOrigin === `anonymous`
				? (t.credentials = `omit`)
				: (t.credentials = `same-origin`),
			t
		);
	}
	function n(e) {
		if (e.ep) return;
		e.ep = !0;
		let n = t(e);
		fetch(e.href, n);
	}
})();
var w = void 0,
	T = typeof window < `u` && window.trustedTypes;
if (T)
	try {
		w = T.createPolicy(`vue`, { createHTML: (e) => e });
	} catch (e) {}
var E = w ? (e) => w.createHTML(e) : (e) => e,
	D = `http://www.w3.org/2000/svg`,
	O = `http://www.w3.org/1998/Math/MathML`,
	k = typeof document < `u` ? document : null,
	_e = k && k.createElement(`template`),
	ve = {
		insert: (e, t, n) => {
			t.insertBefore(e, n || null);
		},
		remove: (e) => {
			let t = e.parentNode;
			t && t.removeChild(e);
		},
		createElement: (e, t, n, r) => {
			let i =
				t === `svg`
					? k.createElementNS(D, e)
					: t === `mathml`
					? k.createElementNS(O, e)
					: n
					? k.createElement(e, { is: n })
					: k.createElement(e);
			return (
				e === `select` &&
					r &&
					r.multiple != null &&
					i.setAttribute(`multiple`, r.multiple),
				i
			);
		},
		createText: (e) => k.createTextNode(e),
		createComment: (e) => k.createComment(e),
		setText: (e, t) => {
			e.nodeValue = t;
		},
		setElementText: (e, t) => {
			e.textContent = t;
		},
		parentNode: (e) => e.parentNode,
		nextSibling: (e) => e.nextSibling,
		querySelector: (e) => k.querySelector(e),
		setScopeId(e, t) {
			e.setAttribute(t, ``);
		},
		insertStaticContent(e, t, n, r, i, a) {
			let o = n ? n.previousSibling : t.lastChild;
			if (i && (i === a || i.nextSibling))
				for (; t.insertBefore(i.cloneNode(!0), n), !(i === a || !(i = i.nextSibling)); );
			else {
				_e.innerHTML = E(
					r === `svg` ? `<svg>${e}</svg>` : r === `mathml` ? `<math>${e}</math>` : e
				);
				let i = _e.content;
				if (r === `svg` || r === `mathml`) {
					let e = i.firstChild;
					for (; e.firstChild; ) i.appendChild(e.firstChild);
					i.removeChild(e);
				}
				t.insertBefore(i, n);
			}
			return [o ? o.nextSibling : t.firstChild, n ? n.previousSibling : t.lastChild];
		},
	},
	ye = Symbol(`_vtc`);
function be(e, t, n) {
	let r = e[ye];
	r && (t = (t ? [t, ...r] : [...r]).join(` `)),
		t == null
			? e.removeAttribute(`class`)
			: n
			? e.setAttribute(`class`, t)
			: (e.className = t);
}
var xe = Symbol(`_vod`),
	Se = Symbol(`_vsh`),
	Ce = Symbol(``),
	we = /(?:^|;)\s*display\s*:/;
function Te(e, t, n) {
	let r = e.style,
		i = s(n),
		a = !1;
	if (n && !i) {
		if (t)
			if (s(t))
				for (let e of t.split(`;`)) {
					let t = e.slice(0, e.indexOf(`:`)).trim();
					n[t] == null && De(r, t, ``);
				}
			else for (let e in t) n[e] == null && De(r, e, ``);
		for (let e in n) e === `display` && (a = !0), De(r, e, n[e]);
	} else if (i) {
		if (t !== n) {
			let e = r[Ce];
			e && (n += `;` + e), (r.cssText = n), (a = we.test(n));
		}
	} else t && e.removeAttribute(`style`);
	xe in e && ((e[xe] = a ? r.display : ``), e[Se] && (r.display = `none`));
}
var Ee = /\s*!important$/;
function De(e, t, n) {
	if (l(n)) n.forEach((n) => De(e, t, n));
	else if ((n == null && (n = ``), t.startsWith(`--`))) e.setProperty(t, n);
	else {
		let r = Ae(e, t);
		Ee.test(n) ? e.setProperty(ee(r), n.replace(Ee, ``), `important`) : (e[r] = n);
	}
}
var Oe = [`Webkit`, `Moz`, `ms`],
	ke = {};
function Ae(e, t) {
	let n = ke[t];
	if (n) return n;
	let r = _(t);
	if (r !== `filter` && r in e) return (ke[t] = r);
	r = u(r);
	for (let n = 0; n < Oe.length; n++) {
		let i = Oe[n] + r;
		if (i in e) return (ke[t] = i);
	}
	return t;
}
var je = `http://www.w3.org/1999/xlink`;
function Me(e, t, n, r, i, o = ie(t)) {
	r && t.startsWith(`xlink:`)
		? n == null
			? e.removeAttributeNS(je, t.slice(6, t.length))
			: e.setAttributeNS(je, t, n)
		: n == null || (o && !a(n))
		? e.removeAttribute(t)
		: e.setAttribute(t, o ? `` : re(n) ? String(n) : n);
}
function Ne(e, t, n, r, i) {
	if (t === `innerHTML` || t === `textContent`) {
		n != null && (e[t] = t === `innerHTML` ? E(n) : n);
		return;
	}
	let o = e.tagName;
	if (t === `value` && o !== `PROGRESS` && !o.includes(`-`)) {
		let r = o === `OPTION` ? e.getAttribute(`value`) || `` : e.value,
			i = n == null ? (e.type === `checkbox` ? `on` : ``) : String(n);
		(r !== i || !(`_value` in e)) && (e.value = i),
			n == null && e.removeAttribute(t),
			(e._value = n);
		return;
	}
	let s = !1;
	if (n === `` || n == null) {
		let r = typeof e[t];
		r === `boolean`
			? (n = a(n))
			: n == null && r === `string`
			? ((n = ``), (s = !0))
			: r === `number` && ((n = 0), (s = !0));
	}
	try {
		e[t] = n;
	} catch (e) {}
	s && e.removeAttribute(i || t);
}
function A(e, t, n, r) {
	e.addEventListener(t, n, r);
}
function Pe(e, t, n, r) {
	e.removeEventListener(t, n, r);
}
var Fe = Symbol(`_vei`);
function Ie(e, t, n, r, i = null) {
	let a = e[Fe] || (e[Fe] = {}),
		o = a[t];
	if (r && o) o.value = r;
	else {
		let [n, s] = Re(t);
		r ? A(e, n, (a[t] = He(r, i)), s) : o && (Pe(e, n, o, s), (a[t] = void 0));
	}
}
var Le = /(?:Once|Passive|Capture)$/;
function Re(e) {
	let t;
	if (Le.test(e)) {
		t = {};
		let n;
		for (; (n = e.match(Le)); )
			(e = e.slice(0, e.length - n[0].length)), (t[n[0].toLowerCase()] = !0);
	}
	return [e[2] === `:` ? e.slice(3) : ee(e.slice(2)), t];
}
var ze = 0,
	Be = Promise.resolve(),
	Ve = () => ze || (Be.then(() => (ze = 0)), (ze = Date.now()));
function He(e, t) {
	let n = (e) => {
		if (!e._vts) e._vts = Date.now();
		else if (e._vts <= n.attached) return;
		ue(Ue(e, n.value), t, 5, [e]);
	};
	return (n.value = e), (n.attached = Ve()), n;
}
function Ue(e, t) {
	if (l(t)) {
		let n = e.stopImmediatePropagation;
		return (
			(e.stopImmediatePropagation = () => {
				n.call(e), (e._stopped = !0);
			}),
			t.map((e) => (t) => !t._stopped && e && e(t))
		);
	} else return t;
}
var We = (e) =>
		e.charCodeAt(0) === 111 &&
		e.charCodeAt(1) === 110 &&
		e.charCodeAt(2) > 96 &&
		e.charCodeAt(2) < 123,
	Ge = (e, n, r, i, a, o) => {
		let c = a === `svg`;
		n === `class`
			? be(e, i, c)
			: n === `style`
			? Te(e, r, i)
			: t(n)
			? me(n) || Ie(e, n, r, i, o)
			: (
					n[0] === `.`
						? ((n = n.slice(1)), !0)
						: n[0] === `^`
						? ((n = n.slice(1)), !1)
						: Ke(e, n, i, c)
			  )
			? (Ne(e, n, i),
			  !e.tagName.includes(`-`) &&
					(n === `value` || n === `checked` || n === `selected`) &&
					Me(e, n, i, c, o, n !== `value`))
			: e._isVueCE && (qe(e, n) || (e._def.__asyncLoader && (/[A-Z]/.test(n) || !s(i))))
			? Ne(e, _(n), i, o, n)
			: (n === `true-value`
					? (e._trueValue = i)
					: n === `false-value` && (e._falseValue = i),
			  Me(e, n, i, c));
	};
function Ke(e, t, n, r) {
	if (r) return !!(t === `innerHTML` || t === `textContent` || (t in e && We(t) && te(n)));
	if (
		t === `spellcheck` ||
		t === `draggable` ||
		t === `translate` ||
		t === `autocorrect` ||
		(t === `sandbox` && e.tagName === `IFRAME`) ||
		t === `form` ||
		(t === `list` && e.tagName === `INPUT`) ||
		(t === `type` && e.tagName === `TEXTAREA`)
	)
		return !1;
	if (t === `width` || t === `height`) {
		let t = e.tagName;
		if (t === `IMG` || t === `VIDEO` || t === `CANVAS` || t === `SOURCE`) return !1;
	}
	return We(t) && s(n) ? !1 : t in e;
}
function qe(e, t) {
	let n = e._def.props;
	if (!n) return !1;
	let r = _(t);
	return Array.isArray(n) ? n.some((e) => _(e) === r) : Object.keys(n).some((e) => _(e) === r);
}
var Je = (e) => {
	let t = e.props[`onUpdate:modelValue`] || !1;
	return l(t) ? (e) => c(t, e) : t;
};
function Ye(e) {
	e.target.composing = !0;
}
function Xe(e) {
	let t = e.target;
	t.composing && ((t.composing = !1), t.dispatchEvent(new Event(`input`)));
}
var Ze = Symbol(`_assign`);
function Qe(e, t, n) {
	return t && (e = e.trim()), n && (e = ae(e)), e;
}
var $e = {
		created(e, { modifiers: { lazy: t, trim: n, number: r } }, i) {
			e[Ze] = Je(i);
			let a = r || (i.props && i.props.type === `number`);
			A(e, t ? `change` : `input`, (t) => {
				t.target.composing || e[Ze](Qe(e.value, n, a));
			}),
				(n || a) &&
					A(e, `change`, () => {
						e.value = Qe(e.value, n, a);
					}),
				t ||
					(A(e, `compositionstart`, Ye), A(e, `compositionend`, Xe), A(e, `change`, Xe));
		},
		mounted(e, { value: t }) {
			e.value = t == null ? `` : t;
		},
		beforeUpdate(e, { value: t, oldValue: n, modifiers: { lazy: r, trim: i, number: a } }, o) {
			if (((e[Ze] = Je(o)), e.composing)) return;
			let s = (a || e.type === `number`) && !/^0\d/.test(e.value) ? ae(e.value) : e.value,
				c = t == null ? `` : t;
			s !== c &&
				((document.activeElement === e &&
					e.type !== `range` &&
					((r && t === n) || (i && e.value.trim() === c))) ||
					(e.value = c));
		},
	},
	et = [`ctrl`, `shift`, `alt`, `meta`],
	tt = {
		stop: (e) => e.stopPropagation(),
		prevent: (e) => e.preventDefault(),
		self: (e) => e.target !== e.currentTarget,
		ctrl: (e) => !e.ctrlKey,
		shift: (e) => !e.shiftKey,
		alt: (e) => !e.altKey,
		meta: (e) => !e.metaKey,
		left: (e) => `button` in e && e.button !== 0,
		middle: (e) => `button` in e && e.button !== 1,
		right: (e) => `button` in e && e.button !== 2,
		exact: (e, t) => et.some((n) => e[`${n}Key`] && !t.includes(n)),
	},
	nt = (e, t) => {
		if (!e) return e;
		let n = e._withMods || (e._withMods = {}),
			r = t.join(`.`);
		return (
			n[r] ||
			(n[r] = (n, ...r) => {
				for (let e = 0; e < t.length; e++) {
					let r = tt[t[e]];
					if (r && r(n, t)) return;
				}
				return e(n, ...r);
			})
		);
	},
	rt = d({ patchProp: Ge }, ve),
	it;
function at() {
	return it || (it = v(rt));
}
var ot = (...e) => {
	let t = at().createApp(...e),
		{ mount: n } = t;
	return (
		(t.mount = (e) => {
			let r = ct(e);
			if (!r) return;
			let i = t._component;
			!te(i) && !i.render && !i.template && (i.template = r.innerHTML),
				r.nodeType === 1 && (r.textContent = ``);
			let a = n(r, !1, st(r));
			return (
				r instanceof Element &&
					(r.removeAttribute(`v-cloak`), r.setAttribute(`data-v-app`, ``)),
				a
			);
		}),
		t
	);
};
function st(e) {
	if (e instanceof SVGElement) return `svg`;
	if (typeof MathMLElement == `function` && e instanceof MathMLElement) return `mathml`;
}
function ct(e) {
	return s(e) ? document.querySelector(e) : e;
}
var lt = (e, t) => {
		let n = e.__vccOpts || e;
		for (let [e, r] of t) n[e] = r;
		return n;
	},
	ut = { inject: [`$auth`] },
	dt = { class: `min-h-screen bg-bp-bg` },
	ft = { key: 0, class: `glass-nav` },
	pt = {
		class: `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14`,
	},
	mt = { class: `flex items-center gap-6` },
	ht = { class: `flex gap-1` },
	gt = { class: `flex items-center gap-3` },
	_t = { class: `text-bp-muted text-sm` },
	vt = { class: `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8` };
function yt(e, t, n, r, i, a) {
	let s = ne(`router-link`),
		c = ne(`router-view`);
	return (
		S(),
		m(`div`, dt, [
			a.$auth.isLoggedIn
				? (S(),
				  m(`nav`, ft, [
						p(`div`, pt, [
							p(`div`, mt, [
								h(
									s,
									{ to: `/`, class: `text-lg font-bold gradient-text` },
									{
										default: pe(() => [
											...(t[1] || (t[1] = [fe(`BenchPress`, -1)])),
										]),
										_: 1,
									}
								),
								p(`div`, ht, [
									h(
										s,
										{
											to: `/`,
											class: o([
												`nav-link`,
												{ "nav-link-active": e.$route.path === `/` },
											]),
										},
										{
											default: pe(() => [
												...(t[2] || (t[2] = [fe(`Labs`, -1)])),
											]),
											_: 1,
										},
										8,
										[`class`]
									),
									h(
										s,
										{
											to: `/benches`,
											class: o([
												`nav-link`,
												{
													"nav-link-active":
														e.$route.path === `/benches`,
												},
											]),
										},
										{
											default: pe(() => [
												...(t[3] || (t[3] = [fe(`Benches`, -1)])),
											]),
											_: 1,
										},
										8,
										[`class`]
									),
								]),
							]),
							p(`div`, gt, [
								p(`span`, _t, le(a.$auth.user), 1),
								p(
									`button`,
									{
										onClick: t[0] || (t[0] = (e) => a.$auth.logout()),
										class: `text-bp-dim hover:text-bp-text text-sm transition-colors`,
									},
									`Logout`
								),
							]),
						]),
				  ]))
				: de(``, !0),
			p(`main`, vt, [h(c)]),
		])
	);
}
var bt = lt(ut, [[`render`, yt]]),
	j = typeof document < `u`;
function xt(e) {
	return typeof e == `object` || `displayName` in e || `props` in e || `__vccOpts` in e;
}
function St(e) {
	return e.__esModule || e[Symbol.toStringTag] === `Module` || (e.default && xt(e.default));
}
var M = Object.assign;
function Ct(e, t) {
	let n = {};
	for (let r in t) {
		let i = t[r];
		n[r] = N(i) ? i.map(e) : e(i);
	}
	return n;
}
var wt = () => {},
	N = Array.isArray;
function Tt(e, t) {
	let n = {};
	for (let r in e) n[r] = r in t ? t[r] : e[r];
	return n;
}
var Et = /#/g,
	Dt = /&/g,
	Ot = /\//g,
	kt = /=/g,
	At = /\?/g,
	jt = /\+/g,
	Mt = /%5B/g,
	Nt = /%5D/g,
	Pt = /%5E/g,
	Ft = /%60/g,
	It = /%7B/g,
	Lt = /%7C/g,
	Rt = /%7D/g,
	zt = /%20/g;
function Bt(e) {
	return e == null
		? ``
		: encodeURI(`` + e)
				.replace(Lt, `|`)
				.replace(Mt, `[`)
				.replace(Nt, `]`);
}
function Vt(e) {
	return Bt(e).replace(It, `{`).replace(Rt, `}`).replace(Pt, `^`);
}
function Ht(e) {
	return Bt(e)
		.replace(jt, `%2B`)
		.replace(zt, `+`)
		.replace(Et, `%23`)
		.replace(Dt, `%26`)
		.replace(Ft, "`")
		.replace(It, `{`)
		.replace(Rt, `}`)
		.replace(Pt, `^`);
}
function Ut(e) {
	return Ht(e).replace(kt, `%3D`);
}
function Wt(e) {
	return Bt(e).replace(Et, `%23`).replace(At, `%3F`);
}
function Gt(e) {
	return Wt(e).replace(Ot, `%2F`);
}
function P(e) {
	if (e == null) return null;
	try {
		return decodeURIComponent(`` + e);
	} catch (e) {}
	return `` + e;
}
var Kt = /\/$/,
	qt = (e) => e.replace(Kt, ``);
function Jt(e, t, n = `/`) {
	let r,
		i = {},
		a = ``,
		o = ``,
		s = t.indexOf(`#`),
		c = t.indexOf(`?`);
	return (
		(c = s >= 0 && c > s ? -1 : c),
		c >= 0 &&
			((r = t.slice(0, c)), (a = t.slice(c, s > 0 ? s : t.length)), (i = e(a.slice(1)))),
		s >= 0 && ((r = r || t.slice(0, s)), (o = t.slice(s, t.length))),
		(r = tn(r == null ? t : r, n)),
		{ fullPath: r + a + o, path: r, query: i, hash: P(o) }
	);
}
function Yt(e, t) {
	let n = t.query ? e(t.query) : ``;
	return t.path + (n && `?`) + n + (t.hash || ``);
}
function Xt(e, t) {
	return !t || !e.toLowerCase().startsWith(t.toLowerCase()) ? e : e.slice(t.length) || `/`;
}
function Zt(e, t, n) {
	let r = t.matched.length - 1,
		i = n.matched.length - 1;
	return (
		r > -1 &&
		r === i &&
		F(t.matched[r], n.matched[i]) &&
		Qt(t.params, n.params) &&
		e(t.query) === e(n.query) &&
		t.hash === n.hash
	);
}
function F(e, t) {
	return (e.aliasOf || e) === (t.aliasOf || t);
}
function Qt(e, t) {
	if (Object.keys(e).length !== Object.keys(t).length) return !1;
	for (var n in e) if (!$t(e[n], t[n])) return !1;
	return !0;
}
function $t(e, t) {
	return N(e)
		? en(e, t)
		: N(t)
		? en(t, e)
		: (e == null ? void 0 : e.valueOf()) === (t == null ? void 0 : t.valueOf());
}
function en(e, t) {
	return N(t)
		? e.length === t.length && e.every((e, n) => e === t[n])
		: e.length === 1 && e[0] === t;
}
function tn(e, t) {
	if (e.startsWith(`/`)) return e;
	if (!e) return t;
	let n = t.split(`/`),
		r = e.split(`/`),
		i = r[r.length - 1];
	(i === `..` || i === `.`) && r.push(``);
	let a = n.length - 1,
		o,
		s;
	for (o = 0; o < r.length; o++)
		if (((s = r[o]), s !== `.`))
			if (s === `..`) a > 1 && a--;
			else break;
	return n.slice(0, a).join(`/`) + `/` + r.slice(o).join(`/`);
}
var I = {
		path: `/`,
		name: void 0,
		params: {},
		query: {},
		hash: ``,
		fullPath: `/`,
		matched: [],
		meta: {},
		redirectedFrom: void 0,
	},
	nn = (function (e) {
		return (e.pop = `pop`), (e.push = `push`), e;
	})({}),
	rn = (function (e) {
		return (e.back = `back`), (e.forward = `forward`), (e.unknown = ``), e;
	})({});
function an(e) {
	if (!e)
		if (j) {
			let t = document.querySelector(`base`);
			(e = (t && t.getAttribute(`href`)) || `/`), (e = e.replace(/^\w+:\/\/[^\/]+/, ``));
		} else e = `/`;
	return e[0] !== `/` && e[0] !== `#` && (e = `/` + e), qt(e);
}
var on = /^[^#]+#/;
function sn(e, t) {
	return e.replace(on, `#`) + t;
}
function cn(e, t) {
	let n = document.documentElement.getBoundingClientRect(),
		r = e.getBoundingClientRect();
	return {
		behavior: t.behavior,
		left: r.left - n.left - (t.left || 0),
		top: r.top - n.top - (t.top || 0),
	};
}
var ln = () => ({ left: window.scrollX, top: window.scrollY });
function un(e) {
	let t;
	if (`el` in e) {
		let n = e.el,
			r = typeof n == `string` && n.startsWith(`#`),
			i =
				typeof n == `string`
					? r
						? document.getElementById(n.slice(1))
						: document.querySelector(n)
					: n;
		if (!i) return;
		t = cn(i, e);
	} else t = e;
	`scrollBehavior` in document.documentElement.style
		? window.scrollTo(t)
		: window.scrollTo(
				t.left == null ? window.scrollX : t.left,
				t.top == null ? window.scrollY : t.top
		  );
}
function dn(e, t) {
	return (history.state ? history.state.position - t : -1) + e;
}
var fn = new Map();
function pn(e, t) {
	fn.set(e, t);
}
function mn(e) {
	let t = fn.get(e);
	return fn.delete(e), t;
}
function hn(e) {
	return typeof e == `string` || (e && typeof e == `object`);
}
function gn(e) {
	return typeof e == `string` || typeof e == `symbol`;
}
var L = (function (e) {
		return (
			(e[(e.MATCHER_NOT_FOUND = 1)] = `MATCHER_NOT_FOUND`),
			(e[(e.NAVIGATION_GUARD_REDIRECT = 2)] = `NAVIGATION_GUARD_REDIRECT`),
			(e[(e.NAVIGATION_ABORTED = 4)] = `NAVIGATION_ABORTED`),
			(e[(e.NAVIGATION_CANCELLED = 8)] = `NAVIGATION_CANCELLED`),
			(e[(e.NAVIGATION_DUPLICATED = 16)] = `NAVIGATION_DUPLICATED`),
			e
		);
	})({}),
	_n = Symbol(``);
L.MATCHER_NOT_FOUND,
	L.NAVIGATION_GUARD_REDIRECT,
	L.NAVIGATION_ABORTED,
	L.NAVIGATION_CANCELLED,
	L.NAVIGATION_DUPLICATED;
function R(e, t) {
	return M(Error(), { type: e, [_n]: !0 }, t);
}
function z(e, t) {
	return e instanceof Error && _n in e && (t == null || !!(e.type & t));
}
function vn(e) {
	let t = {};
	if (e === `` || e === `?`) return t;
	let n = (e[0] === `?` ? e.slice(1) : e).split(`&`);
	for (let e = 0; e < n.length; ++e) {
		let r = n[e].replace(jt, ` `),
			i = r.indexOf(`=`),
			a = P(i < 0 ? r : r.slice(0, i)),
			o = i < 0 ? null : P(r.slice(i + 1));
		if (a in t) {
			let e = t[a];
			N(e) || (e = t[a] = [e]), e.push(o);
		} else t[a] = o;
	}
	return t;
}
function yn(e) {
	let t = ``;
	for (let n in e) {
		let r = e[n];
		if (((n = Ut(n)), r == null)) {
			r !== void 0 && (t += (t.length ? `&` : ``) + n);
			continue;
		}
		(N(r) ? r.map((e) => e && Ht(e)) : [r && Ht(r)]).forEach((e) => {
			e !== void 0 && ((t += (t.length ? `&` : ``) + n), e != null && (t += `=` + e));
		});
	}
	return t;
}
function bn(e) {
	let t = {};
	for (let n in e) {
		let r = e[n];
		r !== void 0 &&
			(t[n] = N(r) ? r.map((e) => (e == null ? null : `` + e)) : r == null ? r : `` + r);
	}
	return t;
}
var xn = Symbol(``),
	Sn = Symbol(``),
	Cn = Symbol(``),
	wn = Symbol(``),
	Tn = Symbol(``);
function B() {
	let e = [];
	function t(t) {
		return (
			e.push(t),
			() => {
				let n = e.indexOf(t);
				n > -1 && e.splice(n, 1);
			}
		);
	}
	function n() {
		e = [];
	}
	return { add: t, list: () => e.slice(), reset: n };
}
function V(e, t, n, r, i, a = (e) => e()) {
	let o = r && (r.enterCallbacks[i] = r.enterCallbacks[i] || []);
	return () =>
		new Promise((s, c) => {
			let l = (e) => {
					e === !1
						? c(R(L.NAVIGATION_ABORTED, { from: n, to: t }))
						: e instanceof Error
						? c(e)
						: hn(e)
						? c(R(L.NAVIGATION_GUARD_REDIRECT, { from: t, to: e }))
						: (o && r.enterCallbacks[i] === o && typeof e == `function` && o.push(e),
						  s());
				},
				u = a(() => e.call(r && r.instances[i], t, n, l)),
				d = Promise.resolve(u);
			e.length < 3 && (d = d.then(l)), d.catch((e) => c(e));
		});
}
function En(e, t, n, r, i = (e) => e()) {
	let a = [];
	for (let o of e)
		for (let e in o.components) {
			let s = o.components[e];
			if (!(t !== `beforeRouteEnter` && !o.instances[e]))
				if (xt(s)) {
					let c = (s.__vccOpts || s)[t];
					c && a.push(V(c, n, r, o, e, i));
				} else {
					let c = s();
					a.push(() =>
						c.then((a) => {
							if (!a)
								throw Error(`Couldn't resolve component "${e}" at "${o.path}"`);
							let s = St(a) ? a.default : a;
							(o.mods[e] = a), (o.components[e] = s);
							let c = (s.__vccOpts || s)[t];
							return c && V(c, n, r, o, e, i)();
						})
					);
				}
		}
	return a;
}
function Dn(e, t) {
	let n = [],
		r = [],
		i = [],
		a = Math.max(t.matched.length, e.matched.length);
	for (let o = 0; o < a; o++) {
		let a = t.matched[o];
		a && (e.matched.find((e) => F(e, a)) ? r.push(a) : n.push(a));
		let s = e.matched[o];
		s && (t.matched.find((e) => F(e, s)) || i.push(s));
	}
	return [n, r, i];
}
var On = () => location.protocol + `//` + location.host;
function kn(e, t) {
	let { pathname: n, search: r, hash: i } = t,
		a = e.indexOf(`#`);
	if (a > -1) {
		let t = i.includes(e.slice(a)) ? e.slice(a).length : 1,
			n = i.slice(t);
		return n[0] !== `/` && (n = `/` + n), Xt(n, ``);
	}
	return Xt(n, e) + r + i;
}
function An(e, t, n, r) {
	let i = [],
		a = [],
		o = null,
		s = ({ state: a }) => {
			let s = kn(e, location),
				c = n.value,
				l = t.value,
				u = 0;
			if (a) {
				if (((n.value = s), (t.value = a), o && o === c)) {
					o = null;
					return;
				}
				u = l ? a.position - l.position : 0;
			} else r(s);
			i.forEach((e) => {
				e(n.value, c, {
					delta: u,
					type: nn.pop,
					direction: u ? (u > 0 ? rn.forward : rn.back) : rn.unknown,
				});
			});
		};
	function c() {
		o = n.value;
	}
	function l(e) {
		i.push(e);
		let t = () => {
			let t = i.indexOf(e);
			t > -1 && i.splice(t, 1);
		};
		return a.push(t), t;
	}
	function u() {
		if (document.visibilityState === `hidden`) {
			let { history: e } = window;
			if (!e.state) return;
			e.replaceState(M({}, e.state, { scroll: ln() }), ``);
		}
	}
	function d() {
		for (let e of a) e();
		(a = []),
			window.removeEventListener(`popstate`, s),
			window.removeEventListener(`pagehide`, u),
			document.removeEventListener(`visibilitychange`, u);
	}
	return (
		window.addEventListener(`popstate`, s),
		window.addEventListener(`pagehide`, u),
		document.addEventListener(`visibilitychange`, u),
		{ pauseListeners: c, listen: l, destroy: d }
	);
}
function jn(e, t, n, r = !1, i = !1) {
	return {
		back: e,
		current: t,
		forward: n,
		replaced: r,
		position: window.history.length,
		scroll: i ? ln() : null,
	};
}
function Mn(e) {
	let { history: t, location: n } = window,
		r = { value: kn(e, n) },
		i = { value: t.state };
	i.value ||
		a(
			r.value,
			{
				back: null,
				current: r.value,
				forward: null,
				position: t.length - 1,
				replaced: !0,
				scroll: null,
			},
			!0
		);
	function a(r, a, o) {
		let s = e.indexOf(`#`),
			c =
				s > -1
					? (n.host && document.querySelector(`base`) ? e : e.slice(s)) + r
					: On() + e + r;
		try {
			t[o ? `replaceState` : `pushState`](a, ``, c), (i.value = a);
		} catch (e) {
			console.error(e), n[o ? `replace` : `assign`](c);
		}
	}
	function o(e, n) {
		a(
			e,
			M({}, t.state, jn(i.value.back, e, i.value.forward, !0), n, {
				position: i.value.position,
			}),
			!0
		),
			(r.value = e);
	}
	function s(e, n) {
		let o = M({}, i.value, t.state, { forward: e, scroll: ln() });
		a(o.current, o, !0),
			a(e, M({}, jn(r.value, e, null), { position: o.position + 1 }, n), !1),
			(r.value = e);
	}
	return { location: r, state: i, push: s, replace: o };
}
function Nn(e) {
	e = an(e);
	let t = Mn(e),
		n = An(e, t.state, t.location, t.replace);
	function r(e, t = !0) {
		t || n.pauseListeners(), history.go(e);
	}
	let i = M({ location: ``, base: e, go: r, createHref: sn.bind(null, e) }, t, n);
	return (
		Object.defineProperty(i, `location`, { enumerable: !0, get: () => t.location.value }),
		Object.defineProperty(i, `state`, { enumerable: !0, get: () => t.state.value }),
		i
	);
}
var H = (function (e) {
		return (
			(e[(e.Static = 0)] = `Static`),
			(e[(e.Param = 1)] = `Param`),
			(e[(e.Group = 2)] = `Group`),
			e
		);
	})({}),
	U = (function (e) {
		return (
			(e[(e.Static = 0)] = `Static`),
			(e[(e.Param = 1)] = `Param`),
			(e[(e.ParamRegExp = 2)] = `ParamRegExp`),
			(e[(e.ParamRegExpEnd = 3)] = `ParamRegExpEnd`),
			(e[(e.EscapeNext = 4)] = `EscapeNext`),
			e
		);
	})(U || {}),
	Pn = { type: H.Static, value: `` },
	Fn = /[a-zA-Z0-9_]/;
function In(e) {
	if (!e) return [[]];
	if (e === `/`) return [[Pn]];
	if (!e.startsWith(`/`)) throw Error(`Invalid path "${e}"`);
	function t(e) {
		throw Error(`ERR (${n})/"${l}": ${e}`);
	}
	let n = U.Static,
		r = n,
		i = [],
		a;
	function o() {
		a && i.push(a), (a = []);
	}
	let s = 0,
		c,
		l = ``,
		u = ``;
	function d() {
		l &&
			(n === U.Static
				? a.push({ type: H.Static, value: l })
				: n === U.Param || n === U.ParamRegExp || n === U.ParamRegExpEnd
				? (a.length > 1 &&
						(c === `*` || c === `+`) &&
						t(`A repeatable param (${l}) must be alone in its segment. eg: '/:ids+.`),
				  a.push({
						type: H.Param,
						value: l,
						regexp: u,
						repeatable: c === `*` || c === `+`,
						optional: c === `*` || c === `?`,
				  }))
				: t(`Invalid state to consume buffer`),
			(l = ``));
	}
	function f() {
		l += c;
	}
	for (; s < e.length; ) {
		if (((c = e[s++]), c === `\\` && n !== U.ParamRegExp)) {
			(r = n), (n = U.EscapeNext);
			continue;
		}
		switch (n) {
			case U.Static:
				c === `/` ? (l && d(), o()) : c === `:` ? (d(), (n = U.Param)) : f();
				break;
			case U.EscapeNext:
				f(), (n = r);
				break;
			case U.Param:
				c === `(`
					? (n = U.ParamRegExp)
					: Fn.test(c)
					? f()
					: (d(), (n = U.Static), c !== `*` && c !== `?` && c !== `+` && s--);
				break;
			case U.ParamRegExp:
				c === `)`
					? u[u.length - 1] == `\\`
						? (u = u.slice(0, -1) + c)
						: (n = U.ParamRegExpEnd)
					: (u += c);
				break;
			case U.ParamRegExpEnd:
				d(), (n = U.Static), c !== `*` && c !== `?` && c !== `+` && s--, (u = ``);
				break;
			default:
				t(`Unknown state`);
				break;
		}
	}
	return n === U.ParamRegExp && t(`Unfinished custom RegExp for param "${l}"`), d(), o(), i;
}
var Ln = `[^/]+?`,
	Rn = { sensitive: !1, strict: !1, start: !0, end: !0 },
	W = (function (e) {
		return (
			(e[(e._multiplier = 10)] = `_multiplier`),
			(e[(e.Root = 90)] = `Root`),
			(e[(e.Segment = 40)] = `Segment`),
			(e[(e.SubSegment = 30)] = `SubSegment`),
			(e[(e.Static = 40)] = `Static`),
			(e[(e.Dynamic = 20)] = `Dynamic`),
			(e[(e.BonusCustomRegExp = 10)] = `BonusCustomRegExp`),
			(e[(e.BonusWildcard = -50)] = `BonusWildcard`),
			(e[(e.BonusRepeatable = -20)] = `BonusRepeatable`),
			(e[(e.BonusOptional = -8)] = `BonusOptional`),
			(e[(e.BonusStrict = 0.7000000000000001)] = `BonusStrict`),
			(e[(e.BonusCaseSensitive = 0.25)] = `BonusCaseSensitive`),
			e
		);
	})(W || {}),
	zn = /[.+*?^${}()[\]/\\]/g;
function Bn(e, t) {
	let n = M({}, Rn, t),
		r = [],
		i = n.start ? `^` : ``,
		a = [];
	for (let t of e) {
		let e = t.length ? [] : [W.Root];
		n.strict && !t.length && (i += `/`);
		for (let r = 0; r < t.length; r++) {
			let o = t[r],
				s = W.Segment + (n.sensitive ? W.BonusCaseSensitive : 0);
			if (o.type === H.Static)
				r || (i += `/`), (i += o.value.replace(zn, `\\$&`)), (s += W.Static);
			else if (o.type === H.Param) {
				let { value: e, repeatable: n, optional: c, regexp: l } = o;
				a.push({ name: e, repeatable: n, optional: c });
				let u = l || Ln;
				if (u !== Ln) {
					s += W.BonusCustomRegExp;
					try {
						`${u}`;
					} catch (t) {
						throw Error(`Invalid custom RegExp for param "${e}" (${u}): ` + t.message);
					}
				}
				let d = n ? `((?:${u})(?:/(?:${u}))*)` : `(${u})`;
				r || (d = c && t.length < 2 ? `(?:/${d})` : `/` + d),
					c && (d += `?`),
					(i += d),
					(s += W.Dynamic),
					c && (s += W.BonusOptional),
					n && (s += W.BonusRepeatable),
					u === `.*` && (s += W.BonusWildcard);
			}
			e.push(s);
		}
		r.push(e);
	}
	if (n.strict && n.end) {
		let e = r.length - 1;
		r[e][r[e].length - 1] += W.BonusStrict;
	}
	n.strict || (i += `/?`), n.end ? (i += `$`) : n.strict && !i.endsWith(`/`) && (i += `(?:/|$)`);
	let o = new RegExp(i, n.sensitive ? `` : `i`);
	function s(e) {
		let t = e.match(o),
			n = {};
		if (!t) return null;
		for (let e = 1; e < t.length; e++) {
			let r = t[e] || ``,
				i = a[e - 1];
			n[i.name] = r && i.repeatable ? r.split(`/`) : r;
		}
		return n;
	}
	function c(t) {
		let n = ``,
			r = !1;
		for (let i of e) {
			(!r || !n.endsWith(`/`)) && (n += `/`), (r = !1);
			for (let e of i)
				if (e.type === H.Static) n += e.value;
				else if (e.type === H.Param) {
					let { value: a, repeatable: o, optional: s } = e,
						c = a in t ? t[a] : ``;
					if (N(c) && !o)
						throw Error(
							`Provided param "${a}" is an array but it is not repeatable (* or + modifiers)`
						);
					let l = N(c) ? c.join(`/`) : c;
					if (!l)
						if (s) i.length < 2 && (n.endsWith(`/`) ? (n = n.slice(0, -1)) : (r = !0));
						else throw Error(`Missing required param "${a}"`);
					n += l;
				}
		}
		return n || `/`;
	}
	return { re: o, score: r, keys: a, parse: s, stringify: c };
}
function Vn(e, t) {
	let n = 0;
	for (; n < e.length && n < t.length; ) {
		let r = t[n] - e[n];
		if (r) return r;
		n++;
	}
	return e.length < t.length
		? e.length === 1 && e[0] === W.Static + W.Segment
			? -1
			: 1
		: e.length > t.length
		? t.length === 1 && t[0] === W.Static + W.Segment
			? 1
			: -1
		: 0;
}
function Hn(e, t) {
	let n = 0,
		r = e.score,
		i = t.score;
	for (; n < r.length && n < i.length; ) {
		let e = Vn(r[n], i[n]);
		if (e) return e;
		n++;
	}
	if (Math.abs(i.length - r.length) === 1) {
		if (Un(r)) return 1;
		if (Un(i)) return -1;
	}
	return i.length - r.length;
}
function Un(e) {
	let t = e[e.length - 1];
	return e.length > 0 && t[t.length - 1] < 0;
}
var Wn = { strict: !1, end: !0, sensitive: !1 };
function Gn(e, t, n) {
	let r = M(Bn(In(e.path), n), { record: e, parent: t, children: [], alias: [] });
	return t && !r.record.aliasOf == !t.record.aliasOf && t.children.push(r), r;
}
function Kn(e, t) {
	let n = [],
		r = new Map();
	t = Tt(Wn, t);
	function i(e) {
		return r.get(e);
	}
	function a(e, n, r) {
		let i = !r,
			s = Jn(e);
		s.aliasOf = r && r.record;
		let l = Tt(t, e),
			u = [s];
		if (`alias` in e) {
			let t = typeof e.alias == `string` ? [e.alias] : e.alias;
			for (let e of t)
				u.push(
					Jn(
						M({}, s, {
							components: r ? r.record.components : s.components,
							path: e,
							aliasOf: r ? r.record : s,
						})
					)
				);
		}
		let d, f;
		for (let t of u) {
			let { path: u } = t;
			if (n && u[0] !== `/`) {
				let e = n.record.path,
					r = e[e.length - 1] === `/` ? `` : `/`;
				t.path = n.record.path + (u && r + u);
			}
			if (
				((d = Gn(t, n, l)),
				r
					? r.alias.push(d)
					: ((f = f || d),
					  f !== d && f.alias.push(d),
					  i && e.name && !Xn(d) && o(e.name)),
				er(d) && c(d),
				s.children)
			) {
				let e = s.children;
				for (let t = 0; t < e.length; t++) a(e[t], d, r && r.children[t]);
			}
			r = r || d;
		}
		return f
			? () => {
					o(f);
			  }
			: wt;
	}
	function o(e) {
		if (gn(e)) {
			let t = r.get(e);
			t &&
				(r.delete(e),
				n.splice(n.indexOf(t), 1),
				t.children.forEach(o),
				t.alias.forEach(o));
		} else {
			let t = n.indexOf(e);
			t > -1 &&
				(n.splice(t, 1),
				e.record.name && r.delete(e.record.name),
				e.children.forEach(o),
				e.alias.forEach(o));
		}
	}
	function s() {
		return n;
	}
	function c(e) {
		let t = Qn(e, n);
		n.splice(t, 0, e), e.record.name && !Xn(e) && r.set(e.record.name, e);
	}
	function l(e, t) {
		let i,
			a = {},
			o,
			s;
		if (`name` in e && e.name) {
			if (((i = r.get(e.name)), !i)) throw R(L.MATCHER_NOT_FOUND, { location: e });
			(s = i.record.name),
				(a = M(
					qn(
						t.params,
						i.keys
							.filter((e) => !e.optional)
							.concat(i.parent ? i.parent.keys.filter((e) => e.optional) : [])
							.map((e) => e.name)
					),
					e.params &&
						qn(
							e.params,
							i.keys.map((e) => e.name)
						)
				)),
				(o = i.stringify(a));
		} else if (e.path != null)
			(o = e.path),
				(i = n.find((e) => e.re.test(o))),
				i && ((a = i.parse(o)), (s = i.record.name));
		else {
			if (((i = t.name ? r.get(t.name) : n.find((e) => e.re.test(t.path))), !i))
				throw R(L.MATCHER_NOT_FOUND, { location: e, currentLocation: t });
			(s = i.record.name), (a = M({}, t.params, e.params)), (o = i.stringify(a));
		}
		let c = [],
			l = i;
		for (; l; ) c.unshift(l.record), (l = l.parent);
		return { name: s, path: o, params: a, matched: c, meta: Zn(c) };
	}
	e.forEach((e) => a(e));
	function u() {
		(n.length = 0), r.clear();
	}
	return {
		addRoute: a,
		resolve: l,
		removeRoute: o,
		clearRoutes: u,
		getRoutes: s,
		getRecordMatcher: i,
	};
}
function qn(e, t) {
	let n = {};
	for (let r of t) r in e && (n[r] = e[r]);
	return n;
}
function Jn(e) {
	let t = {
		path: e.path,
		redirect: e.redirect,
		name: e.name,
		meta: e.meta || {},
		aliasOf: e.aliasOf,
		beforeEnter: e.beforeEnter,
		props: Yn(e),
		children: e.children || [],
		instances: {},
		leaveGuards: new Set(),
		updateGuards: new Set(),
		enterCallbacks: {},
		components:
			`components` in e ? e.components || null : e.component && { default: e.component },
	};
	return Object.defineProperty(t, `mods`, { value: {} }), t;
}
function Yn(e) {
	let t = {},
		n = e.props || !1;
	if (`component` in e) t.default = n;
	else for (let r in e.components) t[r] = typeof n == `object` ? n[r] : n;
	return t;
}
function Xn(e) {
	for (; e; ) {
		if (e.record.aliasOf) return !0;
		e = e.parent;
	}
	return !1;
}
function Zn(e) {
	return e.reduce((e, t) => M(e, t.meta), {});
}
function Qn(e, t) {
	let n = 0,
		r = t.length;
	for (; n !== r; ) {
		let i = (n + r) >> 1;
		Hn(e, t[i]) < 0 ? (r = i) : (n = i + 1);
	}
	let i = $n(e);
	return i && (r = t.lastIndexOf(i, r - 1)), r;
}
function $n(e) {
	let t = e;
	for (; (t = t.parent); ) if (er(t) && Hn(e, t) === 0) return t;
}
function er({ record: e }) {
	return !!(e.name || (e.components && Object.keys(e.components).length) || e.redirect);
}
function tr(t) {
	let n = y(Cn),
		r = y(wn),
		i = g(() => {
			let r = e(t.to);
			return n.resolve(r);
		}),
		a = g(() => {
			let { matched: e } = i.value,
				{ length: t } = e,
				n = e[t - 1],
				a = r.matched;
			if (!n || !a.length) return -1;
			let o = a.findIndex(F.bind(null, n));
			if (o > -1) return o;
			let s = or(e[t - 2]);
			return t > 1 && or(n) === s && a[a.length - 1].path !== s
				? a.findIndex(F.bind(null, e[t - 2]))
				: o;
		}),
		o = g(() => a.value > -1 && ar(r.params, i.value.params)),
		s = g(
			() => a.value > -1 && a.value === r.matched.length - 1 && Qt(r.params, i.value.params)
		);
	function c(r = {}) {
		if (ir(r)) {
			let r = n[e(t.replace) ? `replace` : `push`](e(t.to)).catch(wt);
			return (
				t.viewTransition &&
					typeof document < `u` &&
					`startViewTransition` in document &&
					document.startViewTransition(() => r),
				r
			);
		}
		return Promise.resolve();
	}
	return { route: i, href: g(() => i.value.href), isActive: o, isExactActive: s, navigate: c };
}
function nr(e) {
	return e.length === 1 ? e[0] : e;
}
var rr = oe({
	name: `RouterLink`,
	compatConfig: { MODE: 3 },
	props: {
		to: { type: [String, Object], required: !0 },
		replace: Boolean,
		activeClass: String,
		exactActiveClass: String,
		custom: Boolean,
		ariaCurrentValue: { type: String, default: `page` },
		viewTransition: Boolean,
	},
	useLink: tr,
	setup(e, { slots: t }) {
		let n = i(tr(e)),
			{ options: r } = y(Cn),
			a = g(() => ({
				[sr(e.activeClass, r.linkActiveClass, `router-link-active`)]: n.isActive,
				[sr(e.exactActiveClass, r.linkExactActiveClass, `router-link-exact-active`)]:
					n.isExactActive,
			}));
		return () => {
			let r = t.default && nr(t.default(n));
			return e.custom
				? r
				: b(
						`a`,
						{
							"aria-current": n.isExactActive ? e.ariaCurrentValue : null,
							href: n.href,
							onClick: n.navigate,
							class: a.value,
						},
						r
				  );
		};
	},
});
function ir(e) {
	if (
		!(e.metaKey || e.altKey || e.ctrlKey || e.shiftKey) &&
		!e.defaultPrevented &&
		!(e.button !== void 0 && e.button !== 0)
	) {
		if (e.currentTarget && e.currentTarget.getAttribute) {
			let t = e.currentTarget.getAttribute(`target`);
			if (/\b_blank\b/i.test(t)) return;
		}
		return e.preventDefault && e.preventDefault(), !0;
	}
}
function ar(e, t) {
	for (let n in t) {
		let r = t[n],
			i = e[n];
		if (typeof r == `string`) {
			if (r !== i) return !1;
		} else if (
			!N(i) ||
			i.length !== r.length ||
			r.some((e, t) => e.valueOf() !== i[t].valueOf())
		)
			return !1;
	}
	return !0;
}
function or(e) {
	return e ? (e.aliasOf ? e.aliasOf.path : e.path) : ``;
}
var sr = (e, t, n) => (e == null ? (t == null ? n : t) : e),
	cr = oe({
		name: `RouterView`,
		inheritAttrs: !1,
		props: { name: { type: String, default: `default` }, route: Object },
		compatConfig: { MODE: 3 },
		setup(t, { attrs: i, slots: a }) {
			let o = y(Tn),
				s = g(() => t.route || o.value),
				c = y(Sn, 0),
				l = g(() => {
					let t = e(c),
						{ matched: n } = s.value,
						r;
					for (; (r = n[t]) && !r.components; ) t++;
					return t;
				}),
				u = g(() => s.value.matched[l.value]);
			C(
				Sn,
				g(() => l.value + 1)
			),
				C(xn, u),
				C(Tn, s);
			let d = r();
			return (
				n(
					() => [d.value, u.value, t.name],
					([e, t, n], [r, i, a]) => {
						t &&
							((t.instances[n] = e),
							i &&
								i !== t &&
								e &&
								e === r &&
								(t.leaveGuards.size || (t.leaveGuards = i.leaveGuards),
								t.updateGuards.size || (t.updateGuards = i.updateGuards))),
							e &&
								t &&
								(!i || !F(t, i) || !r) &&
								(t.enterCallbacks[n] || []).forEach((t) => t(e));
					},
					{ flush: `post` }
				),
				() => {
					let e = s.value,
						n = t.name,
						r = u.value,
						o = r && r.components[n];
					if (!o) return lr(a.default, { Component: o, route: e });
					let c = r.props[n],
						l = b(
							o,
							M(
								{},
								c
									? c === !0
										? e.params
										: typeof c == `function`
										? c(e)
										: c
									: null,
								i,
								{
									onVnodeUnmounted: (e) => {
										e.component.isUnmounted && (r.instances[n] = null);
									},
									ref: d,
								}
							)
						);
					return lr(a.default, { Component: l, route: e }) || l;
				}
			);
		},
	});
function lr(e, t) {
	if (!e) return null;
	let n = e(t);
	return n.length === 1 ? n[0] : n;
}
var ur = cr;
function dr(t) {
	let n = Kn(t.routes, t),
		r = t.parseQuery || vn,
		i = t.stringifyQuery || yn,
		a = t.history,
		o = B(),
		s = B(),
		c = B(),
		l = ce(I),
		u = I;
	j &&
		t.scrollBehavior &&
		`scrollRestoration` in history &&
		(history.scrollRestoration = `manual`);
	let d = Ct.bind(null, (e) => `` + e),
		ee = Ct.bind(null, Gt),
		te = Ct.bind(null, P);
	function ne(e, t) {
		let r, i;
		return gn(e) ? ((r = n.getRecordMatcher(e)), (i = t)) : (i = e), n.addRoute(i, r);
	}
	function re(e) {
		let t = n.getRecordMatcher(e);
		t && n.removeRoute(t);
	}
	function ie() {
		return n.getRoutes().map((e) => e.record);
	}
	function ae(e) {
		return !!n.getRecordMatcher(e);
	}
	function p(e, t) {
		if (((t = M({}, t || l.value)), typeof e == `string`)) {
			let i = Jt(r, e, t.path),
				o = n.resolve({ path: i.path }, t),
				s = a.createHref(i.fullPath);
			return M(i, o, {
				params: te(o.params),
				hash: P(i.hash),
				redirectedFrom: void 0,
				href: s,
			});
		}
		let o;
		if (e.path != null) o = M({}, e, { path: Jt(r, e.path, t.path).path });
		else {
			let n = M({}, e.params);
			for (let e in n) n[e] == null && delete n[e];
			(o = M({}, e, { params: ee(n) })), (t.params = ee(t.params));
		}
		let s = n.resolve(o, t),
			c = e.hash || ``;
		s.params = d(te(s.params));
		let u = Yt(i, M({}, e, { hash: Vt(c), path: s.path })),
			f = a.createHref(u);
		return M({ fullPath: u, hash: c, query: i === yn ? bn(e.query) : e.query || {} }, s, {
			redirectedFrom: void 0,
			href: f,
		});
	}
	function m(e) {
		return typeof e == `string` ? Jt(r, e, l.value.path) : M({}, e);
	}
	function h(e, t) {
		if (u !== e) return R(L.NAVIGATION_CANCELLED, { from: t, to: e });
	}
	function oe(e) {
		return v(e);
	}
	function g(e) {
		return oe(M(m(e), { replace: !0 }));
	}
	function _(e, t) {
		let n = e.matched[e.matched.length - 1];
		if (n && n.redirect) {
			let { redirect: r } = n,
				i = typeof r == `function` ? r(e, t) : r;
			return (
				typeof i == `string` &&
					((i = i.includes(`?`) || i.includes(`#`) ? (i = m(i)) : { path: i }),
					(i.params = {})),
				M({ query: e.query, hash: e.hash, params: i.path == null ? e.params : {} }, i)
			);
		}
	}
	function v(e, t) {
		let n = (u = p(e)),
			r = l.value,
			a = e.state,
			o = e.force,
			s = e.replace === !0,
			c = _(n, r);
		if (c)
			return v(
				M(m(c), {
					state: typeof c == `object` ? M({}, a, c.state) : a,
					force: o,
					replace: s,
				}),
				t || n
			);
		let d = n;
		d.redirectedFrom = t;
		let f;
		return (
			!o &&
				Zt(i, r, n) &&
				((f = R(L.NAVIGATION_DUPLICATED, { to: d, from: r })), w(r, r, !0, !1)),
			(f ? Promise.resolve(f) : le(d, r))
				.catch((e) =>
					z(e) ? (z(e, L.NAVIGATION_GUARD_REDIRECT) ? e : ge(e)) : me(e, d, r)
				)
				.then((e) => {
					if (e) {
						if (z(e, L.NAVIGATION_GUARD_REDIRECT))
							return v(
								M({ replace: s }, m(e.to), {
									state: typeof e.to == `object` ? M({}, a, e.to.state) : a,
									force: o,
								}),
								t || d
							);
					} else e = de(d, r, !0, s, a);
					return ue(d, r, e), e;
				})
		);
	}
	function y(e, t) {
		let n = h(e, t);
		return n ? Promise.reject(n) : Promise.resolve();
	}
	function b(e) {
		let t = D.values().next().value;
		return t && typeof t.runWithContext == `function` ? t.runWithContext(e) : e();
	}
	function le(e, t) {
		let n,
			[r, i, a] = Dn(e, t);
		n = En(r.reverse(), `beforeRouteLeave`, e, t);
		for (let i of r)
			i.leaveGuards.forEach((r) => {
				n.push(V(r, e, t));
			});
		let c = y.bind(null, e, t);
		return (
			n.push(c),
			k(n)
				.then(() => {
					n = [];
					for (let r of o.list()) n.push(V(r, e, t));
					return n.push(c), k(n);
				})
				.then(() => {
					n = En(i, `beforeRouteUpdate`, e, t);
					for (let r of i)
						r.updateGuards.forEach((r) => {
							n.push(V(r, e, t));
						});
					return n.push(c), k(n);
				})
				.then(() => {
					n = [];
					for (let r of a)
						if (r.beforeEnter)
							if (N(r.beforeEnter)) for (let i of r.beforeEnter) n.push(V(i, e, t));
							else n.push(V(r.beforeEnter, e, t));
					return n.push(c), k(n);
				})
				.then(
					() => (
						e.matched.forEach((e) => (e.enterCallbacks = {})),
						(n = En(a, `beforeRouteEnter`, e, t, b)),
						n.push(c),
						k(n)
					)
				)
				.then(() => {
					n = [];
					for (let r of s.list()) n.push(V(r, e, t));
					return n.push(c), k(n);
				})
				.catch((e) => (z(e, L.NAVIGATION_CANCELLED) ? e : Promise.reject(e)))
		);
	}
	function ue(e, t, n) {
		c.list().forEach((r) => b(() => r(e, t, n)));
	}
	function de(e, t, n, r, i) {
		let o = h(e, t);
		if (o) return o;
		let s = t === I,
			c = j ? history.state : {};
		n &&
			(r || s
				? a.replace(e.fullPath, M({ scroll: s && c && c.scroll }, i))
				: a.push(e.fullPath, i)),
			(l.value = e),
			w(e, t, n, s),
			ge();
	}
	let x;
	function fe() {
		x ||
			(x = a.listen((e, t, n) => {
				if (!O.listening) return;
				let r = p(e),
					i = _(r, O.currentRoute.value);
				if (i) {
					v(M(i, { replace: !0, force: !0 }), r).catch(wt);
					return;
				}
				u = r;
				let o = l.value;
				j && pn(dn(o.fullPath, n.delta), ln()),
					le(r, o)
						.catch((e) =>
							z(e, L.NAVIGATION_ABORTED | L.NAVIGATION_CANCELLED)
								? e
								: z(e, L.NAVIGATION_GUARD_REDIRECT)
								? (v(M(m(e.to), { force: !0 }), r)
										.then((e) => {
											z(e, L.NAVIGATION_ABORTED | L.NAVIGATION_DUPLICATED) &&
												!n.delta &&
												n.type === nn.pop &&
												a.go(-1, !1);
										})
										.catch(wt),
								  Promise.reject())
								: (n.delta && a.go(-n.delta, !1), me(e, r, o))
						)
						.then((e) => {
							(e = e || de(r, o, !1)),
								e &&
									(n.delta && !z(e, L.NAVIGATION_CANCELLED)
										? a.go(-n.delta, !1)
										: n.type === nn.pop &&
										  z(e, L.NAVIGATION_ABORTED | L.NAVIGATION_DUPLICATED) &&
										  a.go(-1, !1)),
								ue(r, o, e);
						})
						.catch(wt);
			}));
	}
	let S = B(),
		pe = B(),
		C;
	function me(e, t, n) {
		ge(e);
		let r = pe.list();
		return r.length ? r.forEach((r) => r(e, t, n)) : console.error(e), Promise.reject(e);
	}
	function he() {
		return C && l.value !== I
			? Promise.resolve()
			: new Promise((e, t) => {
					S.add([e, t]);
			  });
	}
	function ge(e) {
		return C || ((C = !e), fe(), S.list().forEach(([t, n]) => (e ? n(e) : t())), S.reset()), e;
	}
	function w(e, n, r, i) {
		let { scrollBehavior: a } = t;
		if (!j || !a) return Promise.resolve();
		let o =
			(!r && mn(dn(e.fullPath, 0))) ||
			((i || !r) && history.state && history.state.scroll) ||
			null;
		return se()
			.then(() => a(e, n, o))
			.then((e) => e && un(e))
			.catch((t) => me(t, e, n));
	}
	let T = (e) => a.go(e),
		E,
		D = new Set(),
		O = {
			currentRoute: l,
			listening: !0,
			addRoute: ne,
			removeRoute: re,
			clearRoutes: n.clearRoutes,
			hasRoute: ae,
			getRoutes: ie,
			resolve: p,
			options: t,
			push: oe,
			replace: g,
			go: T,
			back: () => T(-1),
			forward: () => T(1),
			beforeEach: o.add,
			beforeResolve: s.add,
			afterEach: c.add,
			onError: pe.add,
			isReady: he,
			install(t) {
				t.component(`RouterLink`, rr),
					t.component(`RouterView`, ur),
					(t.config.globalProperties.$router = O),
					Object.defineProperty(t.config.globalProperties, `$route`, {
						enumerable: !0,
						get: () => e(l),
					}),
					j && !E && l.value === I && ((E = !0), oe(a.location).catch((e) => {}));
				let n = {};
				for (let e in I)
					Object.defineProperty(n, e, { get: () => l.value[e], enumerable: !0 });
				t.provide(Cn, O), t.provide(wn, f(n)), t.provide(Tn, l);
				let r = t.unmount;
				D.add(t),
					(t.unmount = function () {
						D.delete(t),
							D.size < 1 &&
								((u = I), x && x(), (x = null), (l.value = I), (E = !1), (C = !1)),
							r();
					});
			},
		};
	function k(e) {
		return e.reduce((e, t) => e.then(() => b(t)), Promise.resolve());
	}
	return O;
}
function fr() {
	return y(Cn);
}
function pr(e) {
	return y(wn);
}
var mr = `modulepreload`,
	hr = function (e) {
		return `/assets/benchpress/dashboard/` + e;
	},
	gr = {},
	G = function (e, t, n) {
		let r = Promise.resolve();
		if (t && t.length > 0) {
			let e = document.getElementsByTagName(`link`),
				i = document.querySelector(`meta[property=csp-nonce]`),
				a =
					(i == null ? void 0 : i.nonce) ||
					(i == null ? void 0 : i.getAttribute(`nonce`));
			function o(e) {
				return Promise.all(
					e.map((e) =>
						Promise.resolve(e).then(
							(e) => ({ status: `fulfilled`, value: e }),
							(e) => ({ status: `rejected`, reason: e })
						)
					)
				);
			}
			r = o(
				t.map((t) => {
					if (((t = hr(t, n)), t in gr)) return;
					gr[t] = !0;
					let r = t.endsWith(`.css`),
						i = r ? `[rel="stylesheet"]` : ``;
					if (n)
						for (let n = e.length - 1; n >= 0; n--) {
							let i = e[n];
							if (i.href === t && (!r || i.rel === `stylesheet`)) return;
						}
					else if (document.querySelector(`link[href="${t}"]${i}`)) return;
					let o = document.createElement(`link`);
					if (
						((o.rel = r ? `stylesheet` : mr),
						r || (o.as = `script`),
						(o.crossOrigin = ``),
						(o.href = t),
						a && o.setAttribute(`nonce`, a),
						document.head.appendChild(o),
						r)
					)
						return new Promise((e, n) => {
							o.addEventListener(`load`, e),
								o.addEventListener(`error`, () =>
									n(Error(`Unable to preload CSS for ${t}`))
								);
						});
				})
			);
		}
		function i(e) {
			let t = new Event(`vite:preloadError`, { cancelable: !0 });
			if (((t.payload = e), window.dispatchEvent(t), !t.defaultPrevented)) throw e;
		}
		return r.then((t) => {
			for (let e of t || []) e.status === `rejected` && i(e.reason);
			return e().catch(i);
		});
	},
	_r = [
		{
			path: `/`,
			name: `Labs`,
			component: () => G(() => import(`./LabsPage-seyMQP8C.js`), __vite__mapDeps([0, 1, 2])),
		},
		{
			path: `/benches`,
			name: `Benches`,
			component: () =>
				G(() => import(`./BenchListPage-DweME6wd.js`), __vite__mapDeps([3, 1, 2, 4, 5])),
		},
		{
			path: `/deploy/:lab`,
			name: `Deploy`,
			component: () =>
				G(() => import(`./DeployPage-CiQg8f4-.js`), __vite__mapDeps([6, 1, 2, 5])),
		},
		{
			path: `/bench/:id`,
			name: `BenchDetail`,
			component: () =>
				G(() => import(`./BenchDetailPage-C45h6avy.js`), __vite__mapDeps([7, 1, 2, 4, 5])),
		},
		...[
			{
				path: `/login`,
				name: `Login`,
				component: () => G(() => import(`./Login-hP39zToz.js`), __vite__mapDeps([8, 1])),
				meta: { isLoginPage: !0 },
				props: !0,
			},
		],
	],
	vr = dr({ history: Nn(`/dashboard`), routes: _r });
function yr(e, t) {
	return br.apply(this, arguments);
}
function br() {
	return (
		(br = x(function* (e, t) {
			t || (t = {});
			let n = {
				Accept: `application/json`,
				"Content-Type": `application/json; charset=utf-8`,
				"X-Frappe-Site-Name": window.location.hostname,
			};
			window.csrf_token &&
				window.csrf_token !== `{{ csrf_token }}` &&
				(n[`X-Frappe-CSRF-Token`] = window.csrf_token),
				i(this, `RequestStarted`, null);
			let r = yield fetch(`/api/method/${e}`, {
				method: `POST`,
				headers: n,
				body: JSON.stringify(t),
			});
			if (r.ok) {
				i(this, null, null);
				let t = yield r.json();
				return t.docs || e === `login` ? t : t.message;
			} else {
				let t = yield r.text(),
					n,
					a;
				try {
					n = JSON.parse(t);
				} catch (e) {}
				let o = [[e, n.exc_type, n._error_message].filter(Boolean).join(` `)];
				if (n.exc) {
					a = n.exc;
					try {
						a = JSON.parse(a)[0];
					} catch (e) {}
					o.push(a);
				}
				let s = Error(
					o.join(`
`)
				);
				throw (
					((s.exc_type = n.exc_type),
					(s.exc = a),
					(s.messages = n._server_messages ? JSON.parse(n._server_messages) : []),
					(s.messages = s.messages.concat(n.message)),
					(s.messages = s.messages.map((e) => {
						try {
							return JSON.parse(e).message;
						} catch (t) {
							return e;
						}
					})),
					(s.messages = s.messages.filter(Boolean)),
					s.messages.length ||
						(s.messages = n._error_message
							? [n._error_message]
							: [`Internal Server Error`]),
					i(
						this,
						null,
						s.messages.join(`
`)
					),
					[401, 403].includes(r.status) &&
						vr.currentRoute.name !== `Login` &&
						vr.push(`/login`),
					s)
				);
			}
			function i(e, t, n) {
				(e == null ? void 0 : e.state) !== void 0 && (e.state = t),
					(e == null ? void 0 : e.errorMessage) !== void 0 && (e.errorMessage = n);
			}
		})),
		br.apply(this, arguments)
	);
}
var xr = class {
		constructor(e, t) {
			(this._vm = e), (this._watchers = []);
			let n = i({});
			for (let i in t) {
				let a = t[i];
				if (typeof a == `function`)
					this._watchers.push([
						() => a.call(e),
						(e, t) => this.updateResource(i, e, t),
						{ immediate: !0, deep: !0, flush: `sync` },
					]);
				else {
					let t = new Sr(e, a);
					(n[i] = r(t)), t.auto && t.reload();
				}
			}
			this.resources = n;
		}
		init() {
			this._watchers = this._watchers.map((e) => this._vm.$watch(...e));
		}
		destroy() {
			let e = this._vm;
			delete e._rm;
		}
		updateResource(e, t, n) {
			let r;
			e in this.resources
				? (r = this.resources[e])
				: ((r = i(new Sr(this._vm, t))), (this.resources[e] = r));
			let a = r.data;
			n && r && r.cancel(), r.update(t), r.keepData && (r.data = a), r.auto && r.reload();
		}
	},
	Sr = class {
		constructor(e, t = {}) {
			if ((typeof t == `string` && (t = { method: t, auto: !0 }), !t.method))
				throw Error(`[Resource Manager]: method is required to define a resource`);
			(this._vm = e), (this.method = t.method), (this.delay = t.delay || 0), this.update(t);
		}
		update(e) {
			if (
				(typeof e == `string` && (e = { method: e, auto: !0 }),
				this.method && e.method && e.method !== this.method)
			)
				throw Error(`[Resource Manager]: method cannot change for the same resource`);
			(this.options = e),
				(this.params = e.params || null),
				(this.auto = e.auto || !1),
				(this.keepData = e.keepData || !1),
				(this.condition = e.condition || (() => !0)),
				(this.paged = e.paged || !1),
				(this.validate = e.validate || null),
				this.validate && (this.validate = this.validate.bind(this._vm)),
				(this.listeners = Object.create(null)),
				(this.onceListeners = Object.create(null));
			let t = Object.keys(e).filter((e) => e.startsWith(`on`));
			if (t.length > 0) for (let n of t) this.on(n, e[n]);
			this.reset();
		}
		fetch(e) {
			var t = this;
			return x(function* () {
				if (t.condition()) {
					if (((t.loading = !0), (t.currentParams = e || t.params), t.validate)) {
						let e = yield t.validate();
						if (e) {
							t.setError(e), (t.loading = !1);
							return;
						}
					}
					try {
						let e = yield yr(t.method, t.currentParams);
						t.delay && (yield new Promise((e) => setTimeout(e, t.delay * 1e3))),
							Array.isArray(e) && t.paged
								? ((t.lastPageEmpty = e.length === 0),
								  (t.data = [].concat(t.data || [], e)))
								: (t.data = e),
							t.emit(`Success`, t.data);
					} catch (e) {
						let n = e.messages || [`Internal Server Error`];
						t.setError(
							n.join(`
`)
						);
					}
					(t.lastLoaded = new Date()), (t.loading = !1), (t.currentParams = null);
				}
			})();
		}
		reload() {
			return this.fetch();
		}
		submit(e) {
			return this.fetch(e);
		}
		reset() {
			(this.data = this.options.default || null),
				(this.error = null),
				(this.loading = !1),
				(this.lastLoaded = null),
				(this.lastPageEmpty = !1),
				(this.currentParams = null);
		}
		cancel() {}
		setError(e) {
			(this.error = e), this.emit(`Error`, this.error);
		}
		on(e, t) {
			return (this.listeners[e] = (this.listeners[e] || []).concat(t)), this;
		}
		once(e, t) {
			return (this.onceListeners[e] = (this.onceListeners[e] || []).concat(t)), this;
		}
		emit(e, ...t) {
			let n = `on` + e,
				r = this._vm;
			(this.listeners[n] || []).forEach((e) => {
				i(e);
			}),
				(this.onceListeners[n] || []).forEach((e) => {
					i(e), this.onceListeners[n].splice(this.onceListeners[n].indexOf(e), 1);
				});
			function i(e) {
				try {
					e.call(r, ...t);
				} catch (e) {
					console.error(e);
				}
			}
		}
	};
function Cr(e, t) {
	if (e == null) return {};
	var n = {};
	for (var r in e)
		if ({}.hasOwnProperty.call(e, r)) {
			if (t.includes(r)) continue;
			n[r] = e[r];
		}
	return n;
}
function wr(e, t) {
	if (e == null) return {};
	var n,
		r,
		i = Cr(e, t);
	if (Object.getOwnPropertySymbols) {
		var a = Object.getOwnPropertySymbols(e);
		for (r = 0; r < a.length; r++)
			(n = a[r]), t.includes(n) || ({}.propertyIsEnumerable.call(e, n) && (i[n] = e[n]));
	}
	return i;
}
var Tr = [`$options`],
	Er = {
		beforeCreate() {
			let e = this.$options;
			if (!e.resources || e._rm) return;
			let t;
			if (
				(typeof e.resources == `function` && (e.resources = e.resources.call(this)),
				Or(e.resources))
			) {
				let n = e.resources,
					{ $options: r } = n,
					i = wr(n, Tr);
				t = new xr(this, i);
			} else
				throw Error(
					`[ResourceManager]: resources options should be an object or a function that returns object`
				);
			Object.prototype.hasOwnProperty.call(this, `$resources`) ||
				(this.$resources = i(t.resources)),
				Object.keys(e.resources).forEach((t) => {
					kr(e.computed, t) ||
						kr(e.props, t) ||
						kr(e.methods, t) ||
						(e.computed || (e.computed = {}), (e.computed[t] = e.resources[t]));
				}),
				(this._rm = t);
		},
		data() {
			return this._rm
				? { $rm: this._rm, $r: this._rm.resources, $resources: this._rm.resources }
				: {};
		},
		created() {
			this._rm && this._rm.init();
		},
	};
function Dr(e) {
	e.mixin(Er);
}
function Or(e) {
	return typeof e == `object` && e && Object.prototype.toString(e) === `[object Object]`;
}
function kr(e, t) {
	return t in (e || {});
}
var K = Object.create(null);
(K.open = `0`),
	(K.close = `1`),
	(K.ping = `2`),
	(K.pong = `3`),
	(K.message = `4`),
	(K.upgrade = `5`),
	(K.noop = `6`);
var Ar = Object.create(null);
Object.keys(K).forEach((e) => {
	Ar[K[e]] = e;
});
var jr = { type: `error`, data: `parser error` },
	Mr =
		typeof Blob == `function` ||
		(typeof Blob < `u` && Object.prototype.toString.call(Blob) === `[object BlobConstructor]`),
	Nr = typeof ArrayBuffer == `function`,
	Pr = (e) =>
		typeof ArrayBuffer.isView == `function`
			? ArrayBuffer.isView(e)
			: e && e.buffer instanceof ArrayBuffer,
	Fr = ({ type: e, data: t }, n, r) =>
		Mr && t instanceof Blob
			? n
				? r(t)
				: Ir(t, r)
			: Nr && (t instanceof ArrayBuffer || Pr(t))
			? n
				? r(t)
				: Ir(new Blob([t]), r)
			: r(K[e] + (t || ``)),
	Ir = (e, t) => {
		let n = new FileReader();
		return (
			(n.onload = function () {
				let e = n.result.split(`,`)[1];
				t(`b` + (e || ``));
			}),
			n.readAsDataURL(e)
		);
	};
function Lr(e) {
	return e instanceof Uint8Array
		? e
		: e instanceof ArrayBuffer
		? new Uint8Array(e)
		: new Uint8Array(e.buffer, e.byteOffset, e.byteLength);
}
var Rr;
function zr(e, t) {
	if (Mr && e.data instanceof Blob) return e.data.arrayBuffer().then(Lr).then(t);
	if (Nr && (e.data instanceof ArrayBuffer || Pr(e.data))) return t(Lr(e.data));
	Fr(e, !1, (e) => {
		Rr || (Rr = new TextEncoder()), t(Rr.encode(e));
	});
}
var Br = `ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/`,
	Vr = typeof Uint8Array > `u` ? [] : new Uint8Array(256);
for (let e = 0; e < 64; e++) Vr[Br.charCodeAt(e)] = e;
var Hr = (e) => {
		let t = e.length * 0.75,
			n = e.length,
			r,
			i = 0,
			a,
			o,
			s,
			c;
		e[e.length - 1] === `=` && (t--, e[e.length - 2] === `=` && t--);
		let l = new ArrayBuffer(t),
			u = new Uint8Array(l);
		for (r = 0; r < n; r += 4)
			(a = Vr[e.charCodeAt(r)]),
				(o = Vr[e.charCodeAt(r + 1)]),
				(s = Vr[e.charCodeAt(r + 2)]),
				(c = Vr[e.charCodeAt(r + 3)]),
				(u[i++] = (a << 2) | (o >> 4)),
				(u[i++] = ((o & 15) << 4) | (s >> 2)),
				(u[i++] = ((s & 3) << 6) | (c & 63));
		return l;
	},
	Ur = typeof ArrayBuffer == `function`,
	Wr = (e, t) => {
		if (typeof e != `string`) return { type: `message`, data: Kr(e, t) };
		let n = e.charAt(0);
		return n === `b`
			? { type: `message`, data: Gr(e.substring(1), t) }
			: Ar[n]
			? e.length > 1
				? { type: Ar[n], data: e.substring(1) }
				: { type: Ar[n] }
			: jr;
	},
	Gr = (e, t) => (Ur ? Kr(Hr(e), t) : { base64: !0, data: e }),
	Kr = (e, t) => {
		switch (t) {
			case `blob`:
				return e instanceof Blob ? e : new Blob([e]);
			default:
				return e instanceof ArrayBuffer ? e : e.buffer;
		}
	},
	qr = ``,
	Jr = (e, t) => {
		let n = e.length,
			r = Array(n),
			i = 0;
		e.forEach((e, a) => {
			Fr(e, !1, (e) => {
				(r[a] = e), ++i === n && t(r.join(qr));
			});
		});
	},
	Yr = (e, t) => {
		let n = e.split(qr),
			r = [];
		for (let e = 0; e < n.length; e++) {
			let i = Wr(n[e], t);
			if ((r.push(i), i.type === `error`)) break;
		}
		return r;
	};
function Xr() {
	return new TransformStream({
		transform(e, t) {
			zr(e, (n) => {
				let r = n.length,
					i;
				if (r < 126) (i = new Uint8Array(1)), new DataView(i.buffer).setUint8(0, r);
				else if (r < 65536) {
					i = new Uint8Array(3);
					let e = new DataView(i.buffer);
					e.setUint8(0, 126), e.setUint16(1, r);
				} else {
					i = new Uint8Array(9);
					let e = new DataView(i.buffer);
					e.setUint8(0, 127), e.setBigUint64(1, BigInt(r));
				}
				e.data && typeof e.data != `string` && (i[0] |= 128), t.enqueue(i), t.enqueue(n);
			});
		},
	});
}
var Zr;
function Qr(e) {
	return e.reduce((e, t) => e + t.length, 0);
}
function $r(e, t) {
	if (e[0].length === t) return e.shift();
	let n = new Uint8Array(t),
		r = 0;
	for (let i = 0; i < t; i++) (n[i] = e[0][r++]), r === e[0].length && (e.shift(), (r = 0));
	return e.length && r < e[0].length && (e[0] = e[0].slice(r)), n;
}
function ei(e, t) {
	Zr || (Zr = new TextDecoder());
	let n = [],
		r = 0,
		i = -1,
		a = !1;
	return new TransformStream({
		transform(o, s) {
			for (n.push(o); ; ) {
				if (r === 0) {
					if (Qr(n) < 1) break;
					let e = $r(n, 1);
					(a = (e[0] & 128) == 128),
						(i = e[0] & 127),
						(r = i < 126 ? 3 : i === 126 ? 1 : 2);
				} else if (r === 1) {
					if (Qr(n) < 2) break;
					let e = $r(n, 2);
					(i = new DataView(e.buffer, e.byteOffset, e.length).getUint16(0)), (r = 3);
				} else if (r === 2) {
					if (Qr(n) < 8) break;
					let e = $r(n, 8),
						t = new DataView(e.buffer, e.byteOffset, e.length),
						a = t.getUint32(0);
					if (a > Math.pow(2, 21) - 1) {
						s.enqueue(jr);
						break;
					}
					(i = a * Math.pow(2, 32) + t.getUint32(4)), (r = 3);
				} else {
					if (Qr(n) < i) break;
					let e = $r(n, i);
					s.enqueue(Wr(a ? e : Zr.decode(e), t)), (r = 0);
				}
				if (i === 0 || i > e) {
					s.enqueue(jr);
					break;
				}
			}
		},
	});
}
function q(e) {
	if (e) return ti(e);
}
function ti(e) {
	for (var t in q.prototype) e[t] = q.prototype[t];
	return e;
}
(q.prototype.on = q.prototype.addEventListener =
	function (e, t) {
		return (
			(this._callbacks = this._callbacks || {}),
			(this._callbacks[`$` + e] = this._callbacks[`$` + e] || []).push(t),
			this
		);
	}),
	(q.prototype.once = function (e, t) {
		function n() {
			this.off(e, n), t.apply(this, arguments);
		}
		return (n.fn = t), this.on(e, n), this;
	}),
	(q.prototype.off =
		q.prototype.removeListener =
		q.prototype.removeAllListeners =
		q.prototype.removeEventListener =
			function (e, t) {
				if (((this._callbacks = this._callbacks || {}), arguments.length == 0))
					return (this._callbacks = {}), this;
				var n = this._callbacks[`$` + e];
				if (!n) return this;
				if (arguments.length == 1) return delete this._callbacks[`$` + e], this;
				for (var r, i = 0; i < n.length; i++)
					if (((r = n[i]), r === t || r.fn === t)) {
						n.splice(i, 1);
						break;
					}
				return n.length === 0 && delete this._callbacks[`$` + e], this;
			}),
	(q.prototype.emit = function (e) {
		this._callbacks = this._callbacks || {};
		for (
			var t = Array(arguments.length - 1), n = this._callbacks[`$` + e], r = 1;
			r < arguments.length;
			r++
		)
			t[r - 1] = arguments[r];
		if (n) {
			n = n.slice(0);
			for (var r = 0, i = n.length; r < i; ++r) n[r].apply(this, t);
		}
		return this;
	}),
	(q.prototype.emitReserved = q.prototype.emit),
	(q.prototype.listeners = function (e) {
		return (this._callbacks = this._callbacks || {}), this._callbacks[`$` + e] || [];
	}),
	(q.prototype.hasListeners = function (e) {
		return !!this.listeners(e).length;
	});
var ni =
		typeof Promise == `function` && typeof Promise.resolve == `function`
			? (e) => Promise.resolve().then(e)
			: (e, t) => t(e, 0),
	J = typeof self < `u` ? self : typeof window < `u` ? window : Function(`return this`)(),
	ri = `arraybuffer`;
function ii(e, ...t) {
	return t.reduce((t, n) => (e.hasOwnProperty(n) && (t[n] = e[n]), t), {});
}
var ai = J.setTimeout,
	oi = J.clearTimeout;
function si(e, t) {
	t.useNativeTimers
		? ((e.setTimeoutFn = ai.bind(J)), (e.clearTimeoutFn = oi.bind(J)))
		: ((e.setTimeoutFn = J.setTimeout.bind(J)), (e.clearTimeoutFn = J.clearTimeout.bind(J)));
}
var ci = 1.33;
function li(e) {
	return typeof e == `string` ? ui(e) : Math.ceil((e.byteLength || e.size) * ci);
}
function ui(e) {
	let t = 0,
		n = 0;
	for (let r = 0, i = e.length; r < i; r++)
		(t = e.charCodeAt(r)),
			t < 128
				? (n += 1)
				: t < 2048
				? (n += 2)
				: t < 55296 || t >= 57344
				? (n += 3)
				: (r++, (n += 4));
	return n;
}
function di() {
	return Date.now().toString(36).substring(3) + Math.random().toString(36).substring(2, 5);
}
function fi(e) {
	let t = ``;
	for (let n in e)
		e.hasOwnProperty(n) &&
			(t.length && (t += `&`),
			(t += encodeURIComponent(n) + `=` + encodeURIComponent(e[n])));
	return t;
}
function pi(e) {
	let t = {},
		n = e.split(`&`);
	for (let e = 0, r = n.length; e < r; e++) {
		let r = n[e].split(`=`);
		t[decodeURIComponent(r[0])] = decodeURIComponent(r[1]);
	}
	return t;
}
var mi = class extends Error {
		constructor(e, t, n) {
			super(e), (this.description = t), (this.context = n), (this.type = `TransportError`);
		}
	},
	hi = class extends q {
		constructor(e) {
			super(),
				(this.writable = !1),
				si(this, e),
				(this.opts = e),
				(this.query = e.query),
				(this.socket = e.socket),
				(this.supportsBinary = !e.forceBase64);
		}
		onError(e, t, n) {
			return super.emitReserved(`error`, new mi(e, t, n)), this;
		}
		open() {
			return (this.readyState = `opening`), this.doOpen(), this;
		}
		close() {
			return (
				(this.readyState === `opening` || this.readyState === `open`) &&
					(this.doClose(), this.onClose()),
				this
			);
		}
		send(e) {
			this.readyState === `open` && this.write(e);
		}
		onOpen() {
			(this.readyState = `open`), (this.writable = !0), super.emitReserved(`open`);
		}
		onData(e) {
			let t = Wr(e, this.socket.binaryType);
			this.onPacket(t);
		}
		onPacket(e) {
			super.emitReserved(`packet`, e);
		}
		onClose(e) {
			(this.readyState = `closed`), super.emitReserved(`close`, e);
		}
		pause(e) {}
		createUri(e, t = {}) {
			return e + `://` + this._hostname() + this._port() + this.opts.path + this._query(t);
		}
		_hostname() {
			let e = this.opts.hostname;
			return e.indexOf(`:`) === -1 ? e : `[` + e + `]`;
		}
		_port() {
			return this.opts.port &&
				((this.opts.secure && Number(this.opts.port !== 443)) ||
					(!this.opts.secure && Number(this.opts.port) !== 80))
				? `:` + this.opts.port
				: ``;
		}
		_query(e) {
			let t = fi(e);
			return t.length ? `?` + t : ``;
		}
	},
	gi = class extends hi {
		constructor() {
			super(...arguments), (this._polling = !1);
		}
		get name() {
			return `polling`;
		}
		doOpen() {
			this._poll();
		}
		pause(e) {
			this.readyState = `pausing`;
			let t = () => {
				(this.readyState = `paused`), e();
			};
			if (this._polling || !this.writable) {
				let e = 0;
				this._polling &&
					(e++,
					this.once(`pollComplete`, function () {
						--e || t();
					})),
					this.writable ||
						(e++,
						this.once(`drain`, function () {
							--e || t();
						}));
			} else t();
		}
		_poll() {
			(this._polling = !0), this.doPoll(), this.emitReserved(`poll`);
		}
		onData(e) {
			Yr(e, this.socket.binaryType).forEach((e) => {
				if (
					(this.readyState === `opening` && e.type === `open` && this.onOpen(),
					e.type === `close`)
				)
					return this.onClose({ description: `transport closed by the server` }), !1;
				this.onPacket(e);
			}),
				this.readyState !== `closed` &&
					((this._polling = !1),
					this.emitReserved(`pollComplete`),
					this.readyState === `open` && this._poll());
		}
		doClose() {
			let e = () => {
				this.write([{ type: `close` }]);
			};
			this.readyState === `open` ? e() : this.once(`open`, e);
		}
		write(e) {
			(this.writable = !1),
				Jr(e, (e) => {
					this.doWrite(e, () => {
						(this.writable = !0), this.emitReserved(`drain`);
					});
				});
		}
		uri() {
			let e = this.opts.secure ? `https` : `http`,
				t = this.query || {};
			return (
				!1 !== this.opts.timestampRequests && (t[this.opts.timestampParam] = di()),
				!this.supportsBinary && !t.sid && (t.b64 = 1),
				this.createUri(e, t)
			);
		}
	},
	_i = !1;
try {
	_i = typeof XMLHttpRequest < `u` && `withCredentials` in new XMLHttpRequest();
} catch (e) {}
var vi = _i;
function yi() {}
var bi = class extends gi {
		constructor(e) {
			if ((super(e), typeof location < `u`)) {
				let t = location.protocol === `https:`,
					n = location.port;
				n || (n = t ? `443` : `80`),
					(this.xd =
						(typeof location < `u` && e.hostname !== location.hostname) ||
						n !== e.port);
			}
		}
		doWrite(e, t) {
			let n = this.request({ method: `POST`, data: e });
			n.on(`success`, t),
				n.on(`error`, (e, t) => {
					this.onError(`xhr post error`, e, t);
				});
		}
		doPoll() {
			let e = this.request();
			e.on(`data`, this.onData.bind(this)),
				e.on(`error`, (e, t) => {
					this.onError(`xhr poll error`, e, t);
				}),
				(this.pollXhr = e);
		}
	},
	Y = class e extends q {
		constructor(e, t, n) {
			super(),
				(this.createRequest = e),
				si(this, n),
				(this._opts = n),
				(this._method = n.method || `GET`),
				(this._uri = t),
				(this._data = n.data === void 0 ? null : n.data),
				this._create();
		}
		_create() {
			var t;
			let n = ii(
				this._opts,
				`agent`,
				`pfx`,
				`key`,
				`passphrase`,
				`cert`,
				`ca`,
				`ciphers`,
				`rejectUnauthorized`,
				`autoUnref`
			);
			n.xdomain = !!this._opts.xd;
			let r = (this._xhr = this.createRequest(n));
			try {
				r.open(this._method, this._uri, !0);
				try {
					if (this._opts.extraHeaders) {
						r.setDisableHeaderCheck && r.setDisableHeaderCheck(!0);
						for (let e in this._opts.extraHeaders)
							this._opts.extraHeaders.hasOwnProperty(e) &&
								r.setRequestHeader(e, this._opts.extraHeaders[e]);
					}
				} catch (e) {}
				if (this._method === `POST`)
					try {
						r.setRequestHeader(`Content-type`, `text/plain;charset=UTF-8`);
					} catch (e) {}
				try {
					r.setRequestHeader(`Accept`, `*/*`);
				} catch (e) {}
				(t = this._opts.cookieJar) == null || t.addCookies(r),
					`withCredentials` in r && (r.withCredentials = this._opts.withCredentials),
					this._opts.requestTimeout && (r.timeout = this._opts.requestTimeout),
					(r.onreadystatechange = () => {
						var e;
						r.readyState === 3 &&
							((e = this._opts.cookieJar) == null ||
								e.parseCookies(r.getResponseHeader(`set-cookie`))),
							r.readyState === 4 &&
								(r.status === 200 || r.status === 1223
									? this._onLoad()
									: this.setTimeoutFn(() => {
											this._onError(
												typeof r.status == `number` ? r.status : 0
											);
									  }, 0));
					}),
					r.send(this._data);
			} catch (e) {
				this.setTimeoutFn(() => {
					this._onError(e);
				}, 0);
				return;
			}
			typeof document < `u` &&
				((this._index = e.requestsCount++), (e.requests[this._index] = this));
		}
		_onError(e) {
			this.emitReserved(`error`, e, this._xhr), this._cleanup(!0);
		}
		_cleanup(t) {
			if (!(this._xhr === void 0 || this._xhr === null)) {
				if (((this._xhr.onreadystatechange = yi), t))
					try {
						this._xhr.abort();
					} catch (e) {}
				typeof document < `u` && delete e.requests[this._index], (this._xhr = null);
			}
		}
		_onLoad() {
			let e = this._xhr.responseText;
			e !== null &&
				(this.emitReserved(`data`, e), this.emitReserved(`success`), this._cleanup());
		}
		abort() {
			this._cleanup();
		}
	};
if (((Y.requestsCount = 0), (Y.requests = {}), typeof document < `u`)) {
	if (typeof attachEvent == `function`) attachEvent(`onunload`, xi);
	else if (typeof addEventListener == `function`) {
		let e = `onpagehide` in J ? `pagehide` : `unload`;
		addEventListener(e, xi, !1);
	}
}
function xi() {
	for (let e in Y.requests) Y.requests.hasOwnProperty(e) && Y.requests[e].abort();
}
var Si = (function () {
		let e = wi({ xdomain: !1 });
		return e && e.responseType !== null;
	})(),
	Ci = class extends bi {
		constructor(e) {
			super(e);
			let t = e && e.forceBase64;
			this.supportsBinary = Si && !t;
		}
		request(e = {}) {
			return Object.assign(e, { xd: this.xd }, this.opts), new Y(wi, this.uri(), e);
		}
	};
function wi(e) {
	let t = e.xdomain;
	try {
		if (typeof XMLHttpRequest < `u` && (!t || vi)) return new XMLHttpRequest();
	} catch (e) {}
	if (!t)
		try {
			return new J[[`Active`, `Object`].join(`X`)](`Microsoft.XMLHTTP`);
		} catch (e) {}
}
var Ti =
		typeof navigator < `u` &&
		typeof navigator.product == `string` &&
		navigator.product.toLowerCase() === `reactnative`,
	Ei = class extends hi {
		get name() {
			return `websocket`;
		}
		doOpen() {
			let e = this.uri(),
				t = this.opts.protocols,
				n = Ti
					? {}
					: ii(
							this.opts,
							`agent`,
							`perMessageDeflate`,
							`pfx`,
							`key`,
							`passphrase`,
							`cert`,
							`ca`,
							`ciphers`,
							`rejectUnauthorized`,
							`localAddress`,
							`protocolVersion`,
							`origin`,
							`maxPayload`,
							`family`,
							`checkServerIdentity`
					  );
			this.opts.extraHeaders && (n.headers = this.opts.extraHeaders);
			try {
				this.ws = this.createSocket(e, t, n);
			} catch (e) {
				return this.emitReserved(`error`, e);
			}
			(this.ws.binaryType = this.socket.binaryType), this.addEventListeners();
		}
		addEventListeners() {
			(this.ws.onopen = () => {
				this.opts.autoUnref && this.ws._socket.unref(), this.onOpen();
			}),
				(this.ws.onclose = (e) =>
					this.onClose({ description: `websocket connection closed`, context: e })),
				(this.ws.onmessage = (e) => this.onData(e.data)),
				(this.ws.onerror = (e) => this.onError(`websocket error`, e));
		}
		write(e) {
			this.writable = !1;
			for (let t = 0; t < e.length; t++) {
				let n = e[t],
					r = t === e.length - 1;
				Fr(n, this.supportsBinary, (e) => {
					try {
						this.doWrite(n, e);
					} catch (e) {}
					r &&
						ni(() => {
							(this.writable = !0), this.emitReserved(`drain`);
						}, this.setTimeoutFn);
				});
			}
		}
		doClose() {
			this.ws !== void 0 &&
				((this.ws.onerror = () => {}), this.ws.close(), (this.ws = null));
		}
		uri() {
			let e = this.opts.secure ? `wss` : `ws`,
				t = this.query || {};
			return (
				this.opts.timestampRequests && (t[this.opts.timestampParam] = di()),
				this.supportsBinary || (t.b64 = 1),
				this.createUri(e, t)
			);
		}
	},
	Di = J.WebSocket || J.MozWebSocket,
	Oi = {
		websocket: class extends Ei {
			createSocket(e, t, n) {
				return Ti ? new Di(e, t, n) : t ? new Di(e, t) : new Di(e);
			}
			doWrite(e, t) {
				this.ws.send(t);
			}
		},
		webtransport: class extends hi {
			get name() {
				return `webtransport`;
			}
			doOpen() {
				try {
					this._transport = new WebTransport(
						this.createUri(`https`),
						this.opts.transportOptions[this.name]
					);
				} catch (e) {
					return this.emitReserved(`error`, e);
				}
				this._transport.closed
					.then(() => {
						this.onClose();
					})
					.catch((e) => {
						this.onError(`webtransport error`, e);
					}),
					this._transport.ready.then(() => {
						this._transport.createBidirectionalStream().then((e) => {
							let t = ei(9007199254740991, this.socket.binaryType),
								n = e.readable.pipeThrough(t).getReader(),
								r = Xr();
							r.readable.pipeTo(e.writable), (this._writer = r.writable.getWriter());
							let i = () => {
								n.read()
									.then(({ done: e, value: t }) => {
										e || (this.onPacket(t), i());
									})
									.catch((e) => {});
							};
							i();
							let a = { type: `open` };
							this.query.sid && (a.data = `{"sid":"${this.query.sid}"}`),
								this._writer.write(a).then(() => this.onOpen());
						});
					});
			}
			write(e) {
				this.writable = !1;
				for (let t = 0; t < e.length; t++) {
					let n = e[t],
						r = t === e.length - 1;
					this._writer.write(n).then(() => {
						r &&
							ni(() => {
								(this.writable = !0), this.emitReserved(`drain`);
							}, this.setTimeoutFn);
					});
				}
			}
			doClose() {
				var e;
				(e = this._transport) == null || e.close();
			}
		},
		polling: Ci,
	},
	ki =
		/^(?:(?![^:@\/?#]+:[^:@\/]*@)(http|https|ws|wss):\/\/)?((?:(([^:@\/?#]*)(?::([^:@\/?#]*))?)?@)?((?:[a-f0-9]{0,4}:){2,7}[a-f0-9]{0,4}|[^:\/?#]*)(?::(\d*))?)(((\/(?:[^?#](?![^?#\/]*\.[^?#\/.]+(?:[?#]|$)))*\/?)?([^?#\/]*))(?:\?([^#]*))?(?:#(.*))?)/,
	Ai = [
		`source`,
		`protocol`,
		`authority`,
		`userInfo`,
		`user`,
		`password`,
		`host`,
		`port`,
		`relative`,
		`path`,
		`directory`,
		`file`,
		`query`,
		`anchor`,
	];
function ji(e) {
	if (e.length > 8e3) throw `URI too long`;
	let t = e,
		n = e.indexOf(`[`),
		r = e.indexOf(`]`);
	n != -1 &&
		r != -1 &&
		(e = e.substring(0, n) + e.substring(n, r).replace(/:/g, `;`) + e.substring(r, e.length));
	let i = ki.exec(e || ``),
		a = {},
		o = 14;
	for (; o--; ) a[Ai[o]] = i[o] || ``;
	return (
		n != -1 &&
			r != -1 &&
			((a.source = t),
			(a.host = a.host.substring(1, a.host.length - 1).replace(/;/g, `:`)),
			(a.authority = a.authority.replace(`[`, ``).replace(`]`, ``).replace(/;/g, `:`)),
			(a.ipv6uri = !0)),
		(a.pathNames = Mi(a, a.path)),
		(a.queryKey = Ni(a, a.query)),
		a
	);
}
function Mi(e, t) {
	let n = t.replace(/\/{2,9}/g, `/`).split(`/`);
	return (
		(t.slice(0, 1) == `/` || t.length === 0) && n.splice(0, 1),
		t.slice(-1) == `/` && n.splice(n.length - 1, 1),
		n
	);
}
function Ni(e, t) {
	let n = {};
	return (
		t.replace(/(?:^|&)([^&=]*)=?([^&]*)/g, function (e, t, r) {
			t && (n[t] = r);
		}),
		n
	);
}
var Pi = typeof addEventListener == `function` && typeof removeEventListener == `function`,
	Fi = [];
Pi &&
	addEventListener(
		`offline`,
		() => {
			Fi.forEach((e) => e());
		},
		!1
	);
var Ii = class e extends q {
	constructor(e, t) {
		if (
			(super(),
			(this.binaryType = ri),
			(this.writeBuffer = []),
			(this._prevBufferLen = 0),
			(this._pingInterval = -1),
			(this._pingTimeout = -1),
			(this._maxPayload = -1),
			(this._pingTimeoutTime = 1 / 0),
			e && typeof e == `object` && ((t = e), (e = null)),
			e)
		) {
			let n = ji(e);
			(t.hostname = n.host),
				(t.secure = n.protocol === `https` || n.protocol === `wss`),
				(t.port = n.port),
				n.query && (t.query = n.query);
		} else t.host && (t.hostname = ji(t.host).host);
		si(this, t),
			(this.secure =
				t.secure == null
					? typeof location < `u` && location.protocol === `https:`
					: t.secure),
			t.hostname && !t.port && (t.port = this.secure ? `443` : `80`),
			(this.hostname =
				t.hostname || (typeof location < `u` ? location.hostname : `localhost`)),
			(this.port =
				t.port ||
				(typeof location < `u` && location.port
					? location.port
					: this.secure
					? `443`
					: `80`)),
			(this.transports = []),
			(this._transportsByName = {}),
			t.transports.forEach((e) => {
				let t = e.prototype.name;
				this.transports.push(t), (this._transportsByName[t] = e);
			}),
			(this.opts = Object.assign(
				{
					path: `/engine.io`,
					agent: !1,
					withCredentials: !1,
					upgrade: !0,
					timestampParam: `t`,
					rememberUpgrade: !1,
					addTrailingSlash: !0,
					rejectUnauthorized: !0,
					perMessageDeflate: { threshold: 1024 },
					transportOptions: {},
					closeOnBeforeunload: !1,
				},
				t
			)),
			(this.opts.path =
				this.opts.path.replace(/\/$/, ``) + (this.opts.addTrailingSlash ? `/` : ``)),
			typeof this.opts.query == `string` && (this.opts.query = pi(this.opts.query)),
			Pi &&
				(this.opts.closeOnBeforeunload &&
					((this._beforeunloadEventListener = () => {
						this.transport &&
							(this.transport.removeAllListeners(), this.transport.close());
					}),
					addEventListener(`beforeunload`, this._beforeunloadEventListener, !1)),
				this.hostname !== `localhost` &&
					((this._offlineEventListener = () => {
						this._onClose(`transport close`, {
							description: `network connection lost`,
						});
					}),
					Fi.push(this._offlineEventListener))),
			this.opts.withCredentials && (this._cookieJar = void 0),
			this._open();
	}
	createTransport(e) {
		let t = Object.assign({}, this.opts.query);
		(t.EIO = 4), (t.transport = e), this.id && (t.sid = this.id);
		let n = Object.assign(
			{},
			this.opts,
			{
				query: t,
				socket: this,
				hostname: this.hostname,
				secure: this.secure,
				port: this.port,
			},
			this.opts.transportOptions[e]
		);
		return new this._transportsByName[e](n);
	}
	_open() {
		if (this.transports.length === 0) {
			this.setTimeoutFn(() => {
				this.emitReserved(`error`, `No transports available`);
			}, 0);
			return;
		}
		let t =
			this.opts.rememberUpgrade &&
			e.priorWebsocketSuccess &&
			this.transports.indexOf(`websocket`) !== -1
				? `websocket`
				: this.transports[0];
		this.readyState = `opening`;
		let n = this.createTransport(t);
		n.open(), this.setTransport(n);
	}
	setTransport(e) {
		this.transport && this.transport.removeAllListeners(),
			(this.transport = e),
			e
				.on(`drain`, this._onDrain.bind(this))
				.on(`packet`, this._onPacket.bind(this))
				.on(`error`, this._onError.bind(this))
				.on(`close`, (e) => this._onClose(`transport close`, e));
	}
	onOpen() {
		(this.readyState = `open`),
			(e.priorWebsocketSuccess = this.transport.name === `websocket`),
			this.emitReserved(`open`),
			this.flush();
	}
	_onPacket(e) {
		if (
			this.readyState === `opening` ||
			this.readyState === `open` ||
			this.readyState === `closing`
		)
			switch ((this.emitReserved(`packet`, e), this.emitReserved(`heartbeat`), e.type)) {
				case `open`:
					this.onHandshake(JSON.parse(e.data));
					break;
				case `ping`:
					this._sendPacket(`pong`),
						this.emitReserved(`ping`),
						this.emitReserved(`pong`),
						this._resetPingTimeout();
					break;
				case `error`:
					let t = Error(`server error`);
					(t.code = e.data), this._onError(t);
					break;
				case `message`:
					this.emitReserved(`data`, e.data), this.emitReserved(`message`, e.data);
					break;
			}
	}
	onHandshake(e) {
		this.emitReserved(`handshake`, e),
			(this.id = e.sid),
			(this.transport.query.sid = e.sid),
			(this._pingInterval = e.pingInterval),
			(this._pingTimeout = e.pingTimeout),
			(this._maxPayload = e.maxPayload),
			this.onOpen(),
			this.readyState !== `closed` && this._resetPingTimeout();
	}
	_resetPingTimeout() {
		this.clearTimeoutFn(this._pingTimeoutTimer);
		let e = this._pingInterval + this._pingTimeout;
		(this._pingTimeoutTime = Date.now() + e),
			(this._pingTimeoutTimer = this.setTimeoutFn(() => {
				this._onClose(`ping timeout`);
			}, e)),
			this.opts.autoUnref && this._pingTimeoutTimer.unref();
	}
	_onDrain() {
		this.writeBuffer.splice(0, this._prevBufferLen),
			(this._prevBufferLen = 0),
			this.writeBuffer.length === 0 ? this.emitReserved(`drain`) : this.flush();
	}
	flush() {
		if (
			this.readyState !== `closed` &&
			this.transport.writable &&
			!this.upgrading &&
			this.writeBuffer.length
		) {
			let e = this._getWritablePackets();
			this.transport.send(e), (this._prevBufferLen = e.length), this.emitReserved(`flush`);
		}
	}
	_getWritablePackets() {
		if (
			!(this._maxPayload && this.transport.name === `polling` && this.writeBuffer.length > 1)
		)
			return this.writeBuffer;
		let e = 1;
		for (let t = 0; t < this.writeBuffer.length; t++) {
			let n = this.writeBuffer[t].data;
			if ((n && (e += li(n)), t > 0 && e > this._maxPayload))
				return this.writeBuffer.slice(0, t);
			e += 2;
		}
		return this.writeBuffer;
	}
	_hasPingExpired() {
		if (!this._pingTimeoutTime) return !0;
		let e = Date.now() > this._pingTimeoutTime;
		return (
			e &&
				((this._pingTimeoutTime = 0),
				ni(() => {
					this._onClose(`ping timeout`);
				}, this.setTimeoutFn)),
			e
		);
	}
	write(e, t, n) {
		return this._sendPacket(`message`, e, t, n), this;
	}
	send(e, t, n) {
		return this._sendPacket(`message`, e, t, n), this;
	}
	_sendPacket(e, t, n, r) {
		if (
			(typeof t == `function` && ((r = t), (t = void 0)),
			typeof n == `function` && ((r = n), (n = null)),
			this.readyState === `closing` || this.readyState === `closed`)
		)
			return;
		(n = n || {}), (n.compress = !1 !== n.compress);
		let i = { type: e, data: t, options: n };
		this.emitReserved(`packetCreate`, i),
			this.writeBuffer.push(i),
			r && this.once(`flush`, r),
			this.flush();
	}
	close() {
		let e = () => {
				this._onClose(`forced close`), this.transport.close();
			},
			t = () => {
				this.off(`upgrade`, t), this.off(`upgradeError`, t), e();
			},
			n = () => {
				this.once(`upgrade`, t), this.once(`upgradeError`, t);
			};
		return (
			(this.readyState === `opening` || this.readyState === `open`) &&
				((this.readyState = `closing`),
				this.writeBuffer.length
					? this.once(`drain`, () => {
							this.upgrading ? n() : e();
					  })
					: this.upgrading
					? n()
					: e()),
			this
		);
	}
	_onError(t) {
		if (
			((e.priorWebsocketSuccess = !1),
			this.opts.tryAllTransports &&
				this.transports.length > 1 &&
				this.readyState === `opening`)
		)
			return this.transports.shift(), this._open();
		this.emitReserved(`error`, t), this._onClose(`transport error`, t);
	}
	_onClose(e, t) {
		if (
			this.readyState === `opening` ||
			this.readyState === `open` ||
			this.readyState === `closing`
		) {
			if (
				(this.clearTimeoutFn(this._pingTimeoutTimer),
				this.transport.removeAllListeners(`close`),
				this.transport.close(),
				this.transport.removeAllListeners(),
				Pi &&
					(this._beforeunloadEventListener &&
						removeEventListener(`beforeunload`, this._beforeunloadEventListener, !1),
					this._offlineEventListener))
			) {
				let e = Fi.indexOf(this._offlineEventListener);
				e !== -1 && Fi.splice(e, 1);
			}
			(this.readyState = `closed`),
				(this.id = null),
				this.emitReserved(`close`, e, t),
				(this.writeBuffer = []),
				(this._prevBufferLen = 0);
		}
	}
};
Ii.protocol = 4;
var Li = class extends Ii {
		constructor() {
			super(...arguments), (this._upgrades = []);
		}
		onOpen() {
			if ((super.onOpen(), this.readyState === `open` && this.opts.upgrade))
				for (let e = 0; e < this._upgrades.length; e++) this._probe(this._upgrades[e]);
		}
		_probe(e) {
			let t = this.createTransport(e),
				n = !1;
			Ii.priorWebsocketSuccess = !1;
			let r = () => {
				n ||
					(t.send([{ type: `ping`, data: `probe` }]),
					t.once(`packet`, (e) => {
						if (!n)
							if (e.type === `pong` && e.data === `probe`) {
								if (((this.upgrading = !0), this.emitReserved(`upgrading`, t), !t))
									return;
								(Ii.priorWebsocketSuccess = t.name === `websocket`),
									this.transport.pause(() => {
										n ||
											(this.readyState !== `closed` &&
												(l(),
												this.setTransport(t),
												t.send([{ type: `upgrade` }]),
												this.emitReserved(`upgrade`, t),
												(t = null),
												(this.upgrading = !1),
												this.flush()));
									});
							} else {
								let e = Error(`probe error`);
								(e.transport = t.name), this.emitReserved(`upgradeError`, e);
							}
					}));
			};
			function i() {
				n || ((n = !0), l(), t.close(), (t = null));
			}
			let a = (e) => {
				let n = Error(`probe error: ` + e);
				(n.transport = t.name), i(), this.emitReserved(`upgradeError`, n);
			};
			function o() {
				a(`transport closed`);
			}
			function s() {
				a(`socket closed`);
			}
			function c(e) {
				t && e.name !== t.name && i();
			}
			let l = () => {
				t.removeListener(`open`, r),
					t.removeListener(`error`, a),
					t.removeListener(`close`, o),
					this.off(`close`, s),
					this.off(`upgrading`, c);
			};
			t.once(`open`, r),
				t.once(`error`, a),
				t.once(`close`, o),
				this.once(`close`, s),
				this.once(`upgrading`, c),
				this._upgrades.indexOf(`webtransport`) !== -1 && e !== `webtransport`
					? this.setTimeoutFn(() => {
							n || t.open();
					  }, 200)
					: t.open();
		}
		onHandshake(e) {
			(this._upgrades = this._filterUpgrades(e.upgrades)), super.onHandshake(e);
		}
		_filterUpgrades(e) {
			let t = [];
			for (let n = 0; n < e.length; n++) ~this.transports.indexOf(e[n]) && t.push(e[n]);
			return t;
		}
	},
	Ri = class extends Li {
		constructor(e, t = {}) {
			let n = typeof e == `object` ? e : t;
			(!n.transports || (n.transports && typeof n.transports[0] == `string`)) &&
				(n.transports = (n.transports || [`polling`, `websocket`, `webtransport`])
					.map((e) => Oi[e])
					.filter((e) => !!e)),
				super(e, n);
		}
	};
Ri.protocol;
function zi(e, t = ``, n) {
	let r = e;
	(n = n || (typeof location < `u` && location)),
		e == null && (e = n.protocol + `//` + n.host),
		typeof e == `string` &&
			(e.charAt(0) === `/` && (e = e.charAt(1) === `/` ? n.protocol + e : n.host + e),
			/^(https?|wss?):\/\//.test(e) ||
				(e = n === void 0 ? `https://` + e : n.protocol + `//` + e),
			(r = ji(e))),
		r.port ||
			(/^(http|ws)$/.test(r.protocol)
				? (r.port = `80`)
				: /^(http|ws)s$/.test(r.protocol) && (r.port = `443`)),
		(r.path = r.path || `/`);
	let i = r.host.indexOf(`:`) === -1 ? r.host : `[` + r.host + `]`;
	return (
		(r.id = r.protocol + `://` + i + `:` + r.port + t),
		(r.href = r.protocol + `://` + i + (n && n.port === r.port ? `` : `:` + r.port)),
		r
	);
}
var Bi = typeof ArrayBuffer == `function`,
	Vi = (e) =>
		typeof ArrayBuffer.isView == `function`
			? ArrayBuffer.isView(e)
			: e.buffer instanceof ArrayBuffer,
	Hi = Object.prototype.toString,
	Ui =
		typeof Blob == `function` ||
		(typeof Blob < `u` && Hi.call(Blob) === `[object BlobConstructor]`),
	Wi =
		typeof File == `function` ||
		(typeof File < `u` && Hi.call(File) === `[object FileConstructor]`);
function Gi(e) {
	return (
		(Bi && (e instanceof ArrayBuffer || Vi(e))) ||
		(Ui && e instanceof Blob) ||
		(Wi && e instanceof File)
	);
}
function Ki(e, t) {
	if (!e || typeof e != `object`) return !1;
	if (Array.isArray(e)) {
		for (let t = 0, n = e.length; t < n; t++) if (Ki(e[t])) return !0;
		return !1;
	}
	if (Gi(e)) return !0;
	if (e.toJSON && typeof e.toJSON == `function` && arguments.length === 1)
		return Ki(e.toJSON(), !0);
	for (let t in e) if (Object.prototype.hasOwnProperty.call(e, t) && Ki(e[t])) return !0;
	return !1;
}
function qi(e) {
	let t = [],
		n = e.data,
		r = e;
	return (r.data = Ji(n, t)), (r.attachments = t.length), { packet: r, buffers: t };
}
function Ji(e, t) {
	if (!e) return e;
	if (Gi(e)) {
		let n = { _placeholder: !0, num: t.length };
		return t.push(e), n;
	} else if (Array.isArray(e)) {
		let n = Array(e.length);
		for (let r = 0; r < e.length; r++) n[r] = Ji(e[r], t);
		return n;
	} else if (typeof e == `object` && !(e instanceof Date)) {
		let n = {};
		for (let r in e) Object.prototype.hasOwnProperty.call(e, r) && (n[r] = Ji(e[r], t));
		return n;
	}
	return e;
}
function Yi(e, t) {
	return (e.data = Xi(e.data, t)), delete e.attachments, e;
}
function Xi(e, t) {
	if (!e) return e;
	if (e && e._placeholder === !0) {
		if (typeof e.num == `number` && e.num >= 0 && e.num < t.length) return t[e.num];
		throw Error(`illegal attachments`);
	} else if (Array.isArray(e)) for (let n = 0; n < e.length; n++) e[n] = Xi(e[n], t);
	else if (typeof e == `object`)
		for (let n in e) Object.prototype.hasOwnProperty.call(e, n) && (e[n] = Xi(e[n], t));
	return e;
}
var Zi = ge({ Decoder: () => ta, Encoder: () => $i, PacketType: () => X, protocol: () => 5 }),
	Qi = [
		`connect`,
		`connect_error`,
		`disconnect`,
		`disconnecting`,
		`newListener`,
		`removeListener`,
	],
	X;
(function (e) {
	(e[(e.CONNECT = 0)] = `CONNECT`),
		(e[(e.DISCONNECT = 1)] = `DISCONNECT`),
		(e[(e.EVENT = 2)] = `EVENT`),
		(e[(e.ACK = 3)] = `ACK`),
		(e[(e.CONNECT_ERROR = 4)] = `CONNECT_ERROR`),
		(e[(e.BINARY_EVENT = 5)] = `BINARY_EVENT`),
		(e[(e.BINARY_ACK = 6)] = `BINARY_ACK`);
})(X || (X = {}));
var $i = class {
	constructor(e) {
		this.replacer = e;
	}
	encode(e) {
		return (e.type === X.EVENT || e.type === X.ACK) && Ki(e)
			? this.encodeAsBinary({
					type: e.type === X.EVENT ? X.BINARY_EVENT : X.BINARY_ACK,
					nsp: e.nsp,
					data: e.data,
					id: e.id,
			  })
			: [this.encodeAsString(e)];
	}
	encodeAsString(e) {
		let t = `` + e.type;
		return (
			(e.type === X.BINARY_EVENT || e.type === X.BINARY_ACK) && (t += e.attachments + `-`),
			e.nsp && e.nsp !== `/` && (t += e.nsp + `,`),
			e.id != null && (t += e.id),
			e.data != null && (t += JSON.stringify(e.data, this.replacer)),
			t
		);
	}
	encodeAsBinary(e) {
		let t = qi(e),
			n = this.encodeAsString(t.packet),
			r = t.buffers;
		return r.unshift(n), r;
	}
};
function ea(e) {
	return Object.prototype.toString.call(e) === `[object Object]`;
}
var ta = class e extends q {
		constructor(e) {
			super(), (this.reviver = e);
		}
		add(e) {
			let t;
			if (typeof e == `string`) {
				if (this.reconstructor)
					throw Error(`got plaintext data when reconstructing a packet`);
				t = this.decodeString(e);
				let n = t.type === X.BINARY_EVENT;
				n || t.type === X.BINARY_ACK
					? ((t.type = n ? X.EVENT : X.ACK),
					  (this.reconstructor = new na(t)),
					  t.attachments === 0 && super.emitReserved(`decoded`, t))
					: super.emitReserved(`decoded`, t);
			} else if (Gi(e) || e.base64)
				if (this.reconstructor)
					(t = this.reconstructor.takeBinaryData(e)),
						t && ((this.reconstructor = null), super.emitReserved(`decoded`, t));
				else throw Error(`got binary data when not reconstructing a packet`);
			else throw Error(`Unknown type: ` + e);
		}
		decodeString(t) {
			let n = 0,
				r = { type: Number(t.charAt(0)) };
			if (X[r.type] === void 0) throw Error(`unknown packet type ` + r.type);
			if (r.type === X.BINARY_EVENT || r.type === X.BINARY_ACK) {
				let e = n + 1;
				for (; t.charAt(++n) !== `-` && n != t.length; );
				let i = t.substring(e, n);
				if (i != Number(i) || t.charAt(n) !== `-`) throw Error(`Illegal attachments`);
				r.attachments = Number(i);
			}
			if (t.charAt(n + 1) === `/`) {
				let e = n + 1;
				for (; ++n && !(t.charAt(n) === `,` || n === t.length); );
				r.nsp = t.substring(e, n);
			} else r.nsp = `/`;
			let i = t.charAt(n + 1);
			if (i !== `` && Number(i) == i) {
				let e = n + 1;
				for (; ++n; ) {
					let e = t.charAt(n);
					if (e == null || Number(e) != e) {
						--n;
						break;
					}
					if (n === t.length) break;
				}
				r.id = Number(t.substring(e, n + 1));
			}
			if (t.charAt(++n)) {
				let i = this.tryParse(t.substr(n));
				if (e.isPayloadValid(r.type, i)) r.data = i;
				else throw Error(`invalid payload`);
			}
			return r;
		}
		tryParse(e) {
			try {
				return JSON.parse(e, this.reviver);
			} catch (e) {
				return !1;
			}
		}
		static isPayloadValid(e, t) {
			switch (e) {
				case X.CONNECT:
					return ea(t);
				case X.DISCONNECT:
					return t === void 0;
				case X.CONNECT_ERROR:
					return typeof t == `string` || ea(t);
				case X.EVENT:
				case X.BINARY_EVENT:
					return (
						Array.isArray(t) &&
						(typeof t[0] == `number` ||
							(typeof t[0] == `string` && Qi.indexOf(t[0]) === -1))
					);
				case X.ACK:
				case X.BINARY_ACK:
					return Array.isArray(t);
			}
		}
		destroy() {
			this.reconstructor &&
				(this.reconstructor.finishedReconstruction(), (this.reconstructor = null));
		}
	},
	na = class {
		constructor(e) {
			(this.packet = e), (this.buffers = []), (this.reconPack = e);
		}
		takeBinaryData(e) {
			if ((this.buffers.push(e), this.buffers.length === this.reconPack.attachments)) {
				let e = Yi(this.reconPack, this.buffers);
				return this.finishedReconstruction(), e;
			}
			return null;
		}
		finishedReconstruction() {
			(this.reconPack = null), (this.buffers = []);
		}
	};
function Z(e, t, n) {
	return (
		e.on(t, n),
		function () {
			e.off(t, n);
		}
	);
}
var ra = Object.freeze({
		connect: 1,
		connect_error: 1,
		disconnect: 1,
		disconnecting: 1,
		newListener: 1,
		removeListener: 1,
	}),
	ia = class extends q {
		constructor(e, t, n) {
			super(),
				(this.connected = !1),
				(this.recovered = !1),
				(this.receiveBuffer = []),
				(this.sendBuffer = []),
				(this._queue = []),
				(this._queueSeq = 0),
				(this.ids = 0),
				(this.acks = {}),
				(this.flags = {}),
				(this.io = e),
				(this.nsp = t),
				n && n.auth && (this.auth = n.auth),
				(this._opts = Object.assign({}, n)),
				this.io._autoConnect && this.open();
		}
		get disconnected() {
			return !this.connected;
		}
		subEvents() {
			if (this.subs) return;
			let e = this.io;
			this.subs = [
				Z(e, `open`, this.onopen.bind(this)),
				Z(e, `packet`, this.onpacket.bind(this)),
				Z(e, `error`, this.onerror.bind(this)),
				Z(e, `close`, this.onclose.bind(this)),
			];
		}
		get active() {
			return !!this.subs;
		}
		connect() {
			return this.connected
				? this
				: (this.subEvents(),
				  this.io._reconnecting || this.io.open(),
				  this.io._readyState === `open` && this.onopen(),
				  this);
		}
		open() {
			return this.connect();
		}
		send(...e) {
			return e.unshift(`message`), this.emit.apply(this, e), this;
		}
		emit(e, ...t) {
			var n, r, i;
			if (ra.hasOwnProperty(e))
				throw Error(`"` + e.toString() + `" is a reserved event name`);
			if (
				(t.unshift(e), this._opts.retries && !this.flags.fromQueue && !this.flags.volatile)
			)
				return this._addToQueue(t), this;
			let a = { type: X.EVENT, data: t };
			if (
				((a.options = {}),
				(a.options.compress = this.flags.compress !== !1),
				typeof t[t.length - 1] == `function`)
			) {
				let e = this.ids++,
					n = t.pop();
				this._registerAckCallback(e, n), (a.id = e);
			}
			let o =
					(r = (n = this.io.engine) == null ? void 0 : n.transport) == null
						? void 0
						: r.writable,
				s = this.connected && !((i = this.io.engine) != null && i._hasPingExpired());
			return (
				(this.flags.volatile && !o) ||
					(s
						? (this.notifyOutgoingListeners(a), this.packet(a))
						: this.sendBuffer.push(a)),
				(this.flags = {}),
				this
			);
		}
		_registerAckCallback(e, t) {
			var n;
			let r = (n = this.flags.timeout) == null ? this._opts.ackTimeout : n;
			if (r === void 0) {
				this.acks[e] = t;
				return;
			}
			let i = this.io.setTimeoutFn(() => {
					delete this.acks[e];
					for (let t = 0; t < this.sendBuffer.length; t++)
						this.sendBuffer[t].id === e && this.sendBuffer.splice(t, 1);
					t.call(this, Error(`operation has timed out`));
				}, r),
				a = (...e) => {
					this.io.clearTimeoutFn(i), t.apply(this, e);
				};
			(a.withError = !0), (this.acks[e] = a);
		}
		emitWithAck(e, ...t) {
			return new Promise((n, r) => {
				let i = (e, t) => (e ? r(e) : n(t));
				(i.withError = !0), t.push(i), this.emit(e, ...t);
			});
		}
		_addToQueue(e) {
			let t;
			typeof e[e.length - 1] == `function` && (t = e.pop());
			let n = {
				id: this._queueSeq++,
				tryCount: 0,
				pending: !1,
				args: e,
				flags: Object.assign({ fromQueue: !0 }, this.flags),
			};
			e.push((e, ...r) => {
				if (n === this._queue[0])
					return (
						e === null
							? (this._queue.shift(), t && t(null, ...r))
							: n.tryCount > this._opts.retries && (this._queue.shift(), t && t(e)),
						(n.pending = !1),
						this._drainQueue()
					);
			}),
				this._queue.push(n),
				this._drainQueue();
		}
		_drainQueue(e = !1) {
			if (!this.connected || this._queue.length === 0) return;
			let t = this._queue[0];
			(t.pending && !e) ||
				((t.pending = !0),
				t.tryCount++,
				(this.flags = t.flags),
				this.emit.apply(this, t.args));
		}
		packet(e) {
			(e.nsp = this.nsp), this.io._packet(e);
		}
		onopen() {
			typeof this.auth == `function`
				? this.auth((e) => {
						this._sendConnectPacket(e);
				  })
				: this._sendConnectPacket(this.auth);
		}
		_sendConnectPacket(e) {
			this.packet({
				type: X.CONNECT,
				data: this._pid
					? Object.assign({ pid: this._pid, offset: this._lastOffset }, e)
					: e,
			});
		}
		onerror(e) {
			this.connected || this.emitReserved(`connect_error`, e);
		}
		onclose(e, t) {
			(this.connected = !1),
				delete this.id,
				this.emitReserved(`disconnect`, e, t),
				this._clearAcks();
		}
		_clearAcks() {
			Object.keys(this.acks).forEach((e) => {
				if (!this.sendBuffer.some((t) => String(t.id) === e)) {
					let t = this.acks[e];
					delete this.acks[e],
						t.withError && t.call(this, Error(`socket has been disconnected`));
				}
			});
		}
		onpacket(e) {
			if (e.nsp === this.nsp)
				switch (e.type) {
					case X.CONNECT:
						e.data && e.data.sid
							? this.onconnect(e.data.sid, e.data.pid)
							: this.emitReserved(
									`connect_error`,
									Error(
										`It seems you are trying to reach a Socket.IO server in v2.x with a v3.x client, but they are not compatible (more information here: https://socket.io/docs/v3/migrating-from-2-x-to-3-0/)`
									)
							  );
						break;
					case X.EVENT:
					case X.BINARY_EVENT:
						this.onevent(e);
						break;
					case X.ACK:
					case X.BINARY_ACK:
						this.onack(e);
						break;
					case X.DISCONNECT:
						this.ondisconnect();
						break;
					case X.CONNECT_ERROR:
						this.destroy();
						let t = Error(e.data.message);
						(t.data = e.data.data), this.emitReserved(`connect_error`, t);
						break;
				}
		}
		onevent(e) {
			let t = e.data || [];
			e.id != null && t.push(this.ack(e.id)),
				this.connected ? this.emitEvent(t) : this.receiveBuffer.push(Object.freeze(t));
		}
		emitEvent(e) {
			if (this._anyListeners && this._anyListeners.length) {
				let t = this._anyListeners.slice();
				for (let n of t) n.apply(this, e);
			}
			super.emit.apply(this, e),
				this._pid &&
					e.length &&
					typeof e[e.length - 1] == `string` &&
					(this._lastOffset = e[e.length - 1]);
		}
		ack(e) {
			let t = this,
				n = !1;
			return function (...r) {
				n || ((n = !0), t.packet({ type: X.ACK, id: e, data: r }));
			};
		}
		onack(e) {
			let t = this.acks[e.id];
			typeof t == `function` &&
				(delete this.acks[e.id],
				t.withError && e.data.unshift(null),
				t.apply(this, e.data));
		}
		onconnect(e, t) {
			(this.id = e),
				(this.recovered = t && this._pid === t),
				(this._pid = t),
				(this.connected = !0),
				this.emitBuffered(),
				this.emitReserved(`connect`),
				this._drainQueue(!0);
		}
		emitBuffered() {
			this.receiveBuffer.forEach((e) => this.emitEvent(e)),
				(this.receiveBuffer = []),
				this.sendBuffer.forEach((e) => {
					this.notifyOutgoingListeners(e), this.packet(e);
				}),
				(this.sendBuffer = []);
		}
		ondisconnect() {
			this.destroy(), this.onclose(`io server disconnect`);
		}
		destroy() {
			this.subs && (this.subs.forEach((e) => e()), (this.subs = void 0)),
				this.io._destroy(this);
		}
		disconnect() {
			return (
				this.connected && this.packet({ type: X.DISCONNECT }),
				this.destroy(),
				this.connected && this.onclose(`io client disconnect`),
				this
			);
		}
		close() {
			return this.disconnect();
		}
		compress(e) {
			return (this.flags.compress = e), this;
		}
		get volatile() {
			return (this.flags.volatile = !0), this;
		}
		timeout(e) {
			return (this.flags.timeout = e), this;
		}
		onAny(e) {
			return (
				(this._anyListeners = this._anyListeners || []), this._anyListeners.push(e), this
			);
		}
		prependAny(e) {
			return (
				(this._anyListeners = this._anyListeners || []),
				this._anyListeners.unshift(e),
				this
			);
		}
		offAny(e) {
			if (!this._anyListeners) return this;
			if (e) {
				let t = this._anyListeners;
				for (let n = 0; n < t.length; n++) if (e === t[n]) return t.splice(n, 1), this;
			} else this._anyListeners = [];
			return this;
		}
		listenersAny() {
			return this._anyListeners || [];
		}
		onAnyOutgoing(e) {
			return (
				(this._anyOutgoingListeners = this._anyOutgoingListeners || []),
				this._anyOutgoingListeners.push(e),
				this
			);
		}
		prependAnyOutgoing(e) {
			return (
				(this._anyOutgoingListeners = this._anyOutgoingListeners || []),
				this._anyOutgoingListeners.unshift(e),
				this
			);
		}
		offAnyOutgoing(e) {
			if (!this._anyOutgoingListeners) return this;
			if (e) {
				let t = this._anyOutgoingListeners;
				for (let n = 0; n < t.length; n++) if (e === t[n]) return t.splice(n, 1), this;
			} else this._anyOutgoingListeners = [];
			return this;
		}
		listenersAnyOutgoing() {
			return this._anyOutgoingListeners || [];
		}
		notifyOutgoingListeners(e) {
			if (this._anyOutgoingListeners && this._anyOutgoingListeners.length) {
				let t = this._anyOutgoingListeners.slice();
				for (let n of t) n.apply(this, e.data);
			}
		}
	};
function Q(e) {
	(e = e || {}),
		(this.ms = e.min || 100),
		(this.max = e.max || 1e4),
		(this.factor = e.factor || 2),
		(this.jitter = e.jitter > 0 && e.jitter <= 1 ? e.jitter : 0),
		(this.attempts = 0);
}
(Q.prototype.duration = function () {
	var e = this.ms * Math.pow(this.factor, this.attempts++);
	if (this.jitter) {
		var t = Math.random(),
			n = Math.floor(t * this.jitter * e);
		e = Math.floor(t * 10) & 1 ? e + n : e - n;
	}
	return Math.min(e, this.max) | 0;
}),
	(Q.prototype.reset = function () {
		this.attempts = 0;
	}),
	(Q.prototype.setMin = function (e) {
		this.ms = e;
	}),
	(Q.prototype.setMax = function (e) {
		this.max = e;
	}),
	(Q.prototype.setJitter = function (e) {
		this.jitter = e;
	});
var aa = class extends q {
		constructor(e, t) {
			var n;
			super(),
				(this.nsps = {}),
				(this.subs = []),
				e && typeof e == `object` && ((t = e), (e = void 0)),
				(t = t || {}),
				(t.path = t.path || `/socket.io`),
				(this.opts = t),
				si(this, t),
				this.reconnection(t.reconnection !== !1),
				this.reconnectionAttempts(t.reconnectionAttempts || 1 / 0),
				this.reconnectionDelay(t.reconnectionDelay || 1e3),
				this.reconnectionDelayMax(t.reconnectionDelayMax || 5e3),
				this.randomizationFactor((n = t.randomizationFactor) == null ? 0.5 : n),
				(this.backoff = new Q({
					min: this.reconnectionDelay(),
					max: this.reconnectionDelayMax(),
					jitter: this.randomizationFactor(),
				})),
				this.timeout(t.timeout == null ? 2e4 : t.timeout),
				(this._readyState = `closed`),
				(this.uri = e);
			let r = t.parser || Zi;
			(this.encoder = new r.Encoder()),
				(this.decoder = new r.Decoder()),
				(this._autoConnect = t.autoConnect !== !1),
				this._autoConnect && this.open();
		}
		reconnection(e) {
			return arguments.length
				? ((this._reconnection = !!e), e || (this.skipReconnect = !0), this)
				: this._reconnection;
		}
		reconnectionAttempts(e) {
			return e === void 0
				? this._reconnectionAttempts
				: ((this._reconnectionAttempts = e), this);
		}
		reconnectionDelay(e) {
			var t;
			return e === void 0
				? this._reconnectionDelay
				: ((this._reconnectionDelay = e), (t = this.backoff) == null || t.setMin(e), this);
		}
		randomizationFactor(e) {
			var t;
			return e === void 0
				? this._randomizationFactor
				: ((this._randomizationFactor = e),
				  (t = this.backoff) == null || t.setJitter(e),
				  this);
		}
		reconnectionDelayMax(e) {
			var t;
			return e === void 0
				? this._reconnectionDelayMax
				: ((this._reconnectionDelayMax = e),
				  (t = this.backoff) == null || t.setMax(e),
				  this);
		}
		timeout(e) {
			return arguments.length ? ((this._timeout = e), this) : this._timeout;
		}
		maybeReconnectOnOpen() {
			!this._reconnecting &&
				this._reconnection &&
				this.backoff.attempts === 0 &&
				this.reconnect();
		}
		open(e) {
			if (~this._readyState.indexOf(`open`)) return this;
			this.engine = new Ri(this.uri, this.opts);
			let t = this.engine,
				n = this;
			(this._readyState = `opening`), (this.skipReconnect = !1);
			let r = Z(t, `open`, function () {
					n.onopen(), e && e();
				}),
				i = (t) => {
					this.cleanup(),
						(this._readyState = `closed`),
						this.emitReserved(`error`, t),
						e ? e(t) : this.maybeReconnectOnOpen();
				},
				a = Z(t, `error`, i);
			if (!1 !== this._timeout) {
				let e = this._timeout,
					n = this.setTimeoutFn(() => {
						r(), i(Error(`timeout`)), t.close();
					}, e);
				this.opts.autoUnref && n.unref(),
					this.subs.push(() => {
						this.clearTimeoutFn(n);
					});
			}
			return this.subs.push(r), this.subs.push(a), this;
		}
		connect(e) {
			return this.open(e);
		}
		onopen() {
			this.cleanup(), (this._readyState = `open`), this.emitReserved(`open`);
			let e = this.engine;
			this.subs.push(
				Z(e, `ping`, this.onping.bind(this)),
				Z(e, `data`, this.ondata.bind(this)),
				Z(e, `error`, this.onerror.bind(this)),
				Z(e, `close`, this.onclose.bind(this)),
				Z(this.decoder, `decoded`, this.ondecoded.bind(this))
			);
		}
		onping() {
			this.emitReserved(`ping`);
		}
		ondata(e) {
			try {
				this.decoder.add(e);
			} catch (e) {
				this.onclose(`parse error`, e);
			}
		}
		ondecoded(e) {
			ni(() => {
				this.emitReserved(`packet`, e);
			}, this.setTimeoutFn);
		}
		onerror(e) {
			this.emitReserved(`error`, e);
		}
		socket(e, t) {
			let n = this.nsps[e];
			return (
				n
					? this._autoConnect && !n.active && n.connect()
					: ((n = new ia(this, e, t)), (this.nsps[e] = n)),
				n
			);
		}
		_destroy(e) {
			let t = Object.keys(this.nsps);
			for (let e of t) if (this.nsps[e].active) return;
			this._close();
		}
		_packet(e) {
			let t = this.encoder.encode(e);
			for (let n = 0; n < t.length; n++) this.engine.write(t[n], e.options);
		}
		cleanup() {
			this.subs.forEach((e) => e()), (this.subs.length = 0), this.decoder.destroy();
		}
		_close() {
			(this.skipReconnect = !0), (this._reconnecting = !1), this.onclose(`forced close`);
		}
		disconnect() {
			return this._close();
		}
		onclose(e, t) {
			var n;
			this.cleanup(),
				(n = this.engine) == null || n.close(),
				this.backoff.reset(),
				(this._readyState = `closed`),
				this.emitReserved(`close`, e, t),
				this._reconnection && !this.skipReconnect && this.reconnect();
		}
		reconnect() {
			if (this._reconnecting || this.skipReconnect) return this;
			let e = this;
			if (this.backoff.attempts >= this._reconnectionAttempts)
				this.backoff.reset(),
					this.emitReserved(`reconnect_failed`),
					(this._reconnecting = !1);
			else {
				let t = this.backoff.duration();
				this._reconnecting = !0;
				let n = this.setTimeoutFn(() => {
					e.skipReconnect ||
						(this.emitReserved(`reconnect_attempt`, e.backoff.attempts),
						!e.skipReconnect &&
							e.open((t) => {
								t
									? ((e._reconnecting = !1),
									  e.reconnect(),
									  this.emitReserved(`reconnect_error`, t))
									: e.onreconnect();
							}));
				}, t);
				this.opts.autoUnref && n.unref(),
					this.subs.push(() => {
						this.clearTimeoutFn(n);
					});
			}
		}
		onreconnect() {
			let e = this.backoff.attempts;
			(this._reconnecting = !1), this.backoff.reset(), this.emitReserved(`reconnect`, e);
		}
	},
	oa = {};
function sa(e, t) {
	typeof e == `object` && ((t = e), (e = void 0)), (t = t || {});
	let n = zi(e, t.path || `/socket.io`),
		r = n.source,
		i = n.id,
		a = n.path,
		o = oa[i] && a in oa[i].nsps,
		s = t.forceNew || t[`force new connection`] || !1 === t.multiplex || o,
		c;
	return (
		s ? (c = new aa(r, t)) : (oa[i] || (oa[i] = new aa(r, t)), (c = oa[i])),
		n.query && !t.query && (t.query = n.queryKey),
		c.socket(n.path, t)
	);
}
Object.assign(sa, { Manager: aa, Socket: ia, io: sa, connect: sa });
var ca = window.location.hostname,
	la = window.location.port ? `:9000` : ``,
	ua = sa(`${la ? `http` : `https`}://${ca}${la}`),
	da = class {
		constructor() {
			(this.isLoggedIn = !1),
				(this.user = null),
				(this.user_image = null),
				(this.cookie = null),
				(this.cookie = Object.fromEntries(
					document.cookie
						.split(`; `)
						.map((e) => e.split(`=`))
						.map((e) => [e[0], decodeURIComponent(e[1])])
				)),
				(this.isLoggedIn = this.cookie.user_id && this.cookie.user_id !== `Guest`);
		}
		login(e, t) {
			var n = this;
			return x(function* () {
				let r = yield yr(`login`, { usr: e, pwd: t });
				return r ? ((n.isLoggedIn = !0), r) : !1;
			})();
		}
		logout() {
			var e = this;
			return x(function* () {
				yield yr(`logout`), (e.isLoggedIn = !1), window.location.reload();
			})();
		}
		resetPassword(e) {
			return x(function* () {
				console.log(`resetting password`);
			})();
		}
	},
	$ = ot(bt),
	fa = i(new da());
$.use(vr),
	$.use(Dr),
	$.provide(`$auth`, fa),
	$.provide(`$call`, yr),
	$.provide(`$socket`, ua),
	vr.beforeEach(
		(function () {
			var e = x(function* (e, t, n) {
				e.matched.some((e) => !e.meta.isLoginPage)
					? fa.isLoggedIn
						? n()
						: n({ name: `Login`, query: { route: e.path } })
					: fa.isLoggedIn
					? n({ name: `Home` })
					: n();
			});
			return function (t, n, r) {
				return e.apply(this, arguments);
			};
		})()
	),
	$.mount(`#app`);
export { nt as a, $e as i, fr as n, lt as r, pr as t };
