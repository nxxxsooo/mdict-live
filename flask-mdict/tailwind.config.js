/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./flask_mdict/templates/**/*.html",
    "./flask_mdict/static/**/*.js"
  ],
  theme: {
    extend: {},
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light", "dark", "cupcake"],
  },
}
