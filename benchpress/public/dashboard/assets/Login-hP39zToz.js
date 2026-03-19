import { T as e, a as t, c as n, t as r, v as i } from "./asyncToGenerator-xMs8Wj7k.js";
import { a, i as o, r as s } from "./index-ifQeZ2Ak.js";
var c = {
		data() {
			return { email: null, password: null };
		},
		inject: [`$auth`],
		mounted() {
			var e = this;
			return r(function* () {
				var t;
				!((t = e.$route) == null || (t = t.query) == null) &&
					t.route &&
					((e.redirect_route = e.$route.query.route),
					e.$router.replace({ query: null }));
			})();
		},
		methods: {
			login() {
				var e = this;
				return r(function* () {
					e.email &&
						e.password &&
						(yield e.$auth.login(e.email, e.password)) &&
						e.$router.push({ name: `Home` });
				})();
			},
		},
	},
	l = { class: `min-h-screen bg-white flex` },
	u = { class: `mx-auto w-full max-w-sm lg:w-96` };
function d(r, s, c, d, f, p) {
	return (
		i(),
		n(`div`, l, [
			t(`div`, u, [
				t(
					`form`,
					{
						onSubmit:
							s[2] || (s[2] = a((...e) => p.login && p.login(...e), [`prevent`])),
						class: `space-y-6`,
					},
					[
						s[3] || (s[3] = t(`label`, { for: `email` }, ` Username: `, -1)),
						e(
							t(
								`input`,
								{
									type: `text`,
									"onUpdate:modelValue": s[0] || (s[0] = (e) => (f.email = e)),
								},
								null,
								512
							),
							[[o, f.email]]
						),
						s[4] || (s[4] = t(`br`, null, null, -1)),
						s[5] || (s[5] = t(`label`, { for: `password` }, ` Password: `, -1)),
						e(
							t(
								`input`,
								{
									type: `password`,
									"onUpdate:modelValue":
										s[1] || (s[1] = (e) => (f.password = e)),
								},
								null,
								512
							),
							[[o, f.password]]
						),
						s[6] ||
							(s[6] = t(
								`button`,
								{
									class: `bg-blue-500 block text-white p-2 hover:bg-blue-700`,
									type: `submit`,
								},
								` Sign in `,
								-1
							)),
					],
					32
				),
			]),
		])
	);
}
var f = s(c, [[`render`, d]]);
export { f as default };
