// Lightweight offline reverse-geocoder using bounding boxes for major emitting regions

const COUNTRY_BBOXES = [
  { name: 'United States', bounds: { n: 49.38, s: 24.39, w: -125.0, e: -66.93 } },
  { name: 'Canada', bounds: { n: 83.11, s: 41.67, w: -141.0, e: -52.62 } },
  { name: 'Russia', bounds: { n: 81.86, s: 41.19, w: 19.64, e: -169.05 } }, // Simplified
  { name: 'China', bounds: { n: 53.56, s: 18.16, w: 73.5, e: 134.77 } },
  { name: 'India', bounds: { n: 35.5, s: 6.75, w: 68.16, e: 97.4 } },
  { name: 'Brazil', bounds: { n: 5.27, s: -33.75, w: -73.98, e: -34.79 } },
  { name: 'Australia', bounds: { n: -10.06, s: -43.63, w: 112.9, e: 153.63 } },
  { name: 'Saudi Arabia', bounds: { n: 32.15, s: 16.39, w: 34.57, e: 55.66 } },
  { name: 'Iran', bounds: { n: 39.78, s: 25.06, w: 44.05, e: 63.33 } },
  { name: 'Mexico', bounds: { n: 32.72, s: 14.54, w: -118.36, e: -86.71 } },
  { name: 'Algeria', bounds: { n: 37.09, s: 18.96, w: -8.67, e: 11.98 } },
  { name: 'Venezuela', bounds: { n: 12.11, s: 0.66, w: -73.38, e: -59.8 } },
]

export function getCountryFromCoordinates(lat, lon) {
  if (lat == null || lon == null) return 'Unknown Region'

  // Normalize longitude for crossing antimeridian (not handling Russia fully here for simplicity)
  for (const country of COUNTRY_BBOXES) {
    if (lat <= country.bounds.n && lat >= country.bounds.s) {
      if (country.bounds.w > country.bounds.e) {
        // Crosses dateline (like Russia)
        if (lon >= country.bounds.w || lon <= country.bounds.e) {
          return country.name
        }
      } else {
        if (lon >= country.bounds.w && lon <= country.bounds.e) {
          return country.name
        }
      }
    }
  }

  // Fallback regions based on general lat/lon
  if (lat > 60) return 'Arctic Region'
  if (lat > 35 && lon > -10 && lon < 40) return 'Europe'
  if (lat > -35 && lat < 35 && lon > -20 && lon < 50) return 'Africa'
  if (lat < -50) return 'Antarctica'

  return 'International Waters'
}
