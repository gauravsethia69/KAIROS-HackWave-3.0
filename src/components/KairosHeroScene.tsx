/** Decorative landscape only. One solid blood-red sun, Mount Fuji, a torii and sakura.
 * Kept separate from business logic; the scene cannot intercept pointer events.
 */
const flowers: Array<[number, number, number, number]> = [
  [475, 33, 1.06, 12], [510, 54, 0.9, -18], [539, 82, 0.95, 20],
  [564, 31, 0.72, 8], [601, 39, 1.04, -7], [631, 10, 0.8, 12],
  [655, 61, 1.18, -12], [693, 29, 0.91, 15], [728, 70, 0.85, 8],
  [764, 42, 1.15, -20], [578, 97, 0.76, 25], [686, 91, 0.78, -3],
  [741, 14, 0.77, 14], [459, 71, 0.62, -12], [612, 83, 0.66, 7],
];
const petals: Array<[number,number,number]> = [
  [341, 96, 11], [411, 171, -29], [446, 113, 26], [501, 142, 17], [558, 180, -18],
  [674, 119, 24], [760, 153, -20], [374, 250, 20], [613, 273, -36], [727, 235, 14],
];

export function KairosHeroScene() {
  return (
    <div className="kairos-hero-art" aria-hidden="true">
      <svg className="kairos-hero-svg" viewBox="0 0 780 355" fill="none" xmlns="http://www.w3.org/2000/svg" focusable="false">
        <defs>
          <linearGradient id="kairos-scene-fade" x1="0" x2="1" y1="0" y2="0"><stop stopColor="white" stopOpacity="0"/><stop offset="0.21" stopColor="white" stopOpacity="0.55"/><stop offset="0.45" stopColor="white"/><stop offset="1" stopColor="white"/></linearGradient>
          <linearGradient id="kairos-fuji-mist" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#83939A" stopOpacity="0.85"/><stop offset="1" stopColor="#AEB4AF" stopOpacity="0.18"/></linearGradient>
          <pattern id="kairos-seigaiha" x="0" y="0" width="54" height="24" patternUnits="userSpaceOnUse"><path d="M-27 24A27 27 0 0 1 27 24M0 24A27 27 0 0 1 54 24M-13.5 24A13.5 13.5 0 0 1 13.5 24M13.5 24A13.5 13.5 0 0 1 40.5 24M40.5 24A13.5 13.5 0 0 1 67.5 24" stroke="#CEA878" strokeWidth="1" opacity="0.25"/></pattern>
          <mask id="kairos-scene-mask"><rect width="780" height="355" fill="url(#kairos-scene-fade)"/></mask>
        </defs>
        <g mask="url(#kairos-scene-mask)">
          {/* Faint Japanese cloud strokes, kept behind the sun and mountain. */}
          <g stroke="#D6A97E" strokeWidth="1.3" opacity="0.42" strokeLinecap="round">
            <path d="M265 55h56c18 0 20-10 5-10h-14c-17 0-13-13 3-13h47"/>
            <path d="M313 65h103c20 0 24-14 7-14h-25"/>
            <path d="M395 118h57c15 0 17-11 3-11h-20"/>
            <path d="M590 205h43c23 0 20-10 6-10h-10c-13 0-13-10 0-10h76"/>
            <path d="M689 196h71c24 0 18-11 7-11h-15"/>
          </g>
          {/* Exactly one solid blood-red rising sun. */}
          <circle cx="644" cy="181" r="89" fill="#9E1628"/>
          {/* Mount Fuji and ridges rendered in muted, ink-wash geometry. */}
          <path d="M379 319 529 256 589 218 628 194 658 220 725 271 780 305v47H379Z" fill="#B2B6AF" opacity="0.31"/>
          <path d="m386 324 104-43 88-76 37-33 34 40 92 77 39 23v43H386Z" fill="url(#kairos-fuji-mist)"/>
          <path d="m540 239 38-34 37-33 34 40 19 15-27-9-13 5-13-21-14 16-16-5-13 21-20-2Z" fill="#F8F4EE"/>
          <path d="m588 210-25 31 19-15 6-16Zm29-17 14 36-3-25-11-11Zm24 25 29 30-15-28-14-2Z" fill="#687A83" opacity=".82"/>
          <path d="m451 317 87-53 27-13-83 64m122-69 77 55-53-38m-123 62 77-52" stroke="#647B86" opacity=".34" strokeWidth="2"/>
          {/* A restrained torii silhouette, with no text or interactivity. */}
          <g transform="translate(714 232)" fill="#731728" stroke="#681320" strokeLinejoin="round">
            <path d="M-41-6h88l7-7c-33 5-68 5-102-1l7 8Z"/>
            <path d="M-35 4h77v8h-77zM-31 12h8v63h-8zM27 12h8v63h-8z"/>
          </g>
          {/* Birds. */}
          <g stroke="#20303D" strokeWidth="2.2" strokeLinecap="round" opacity=".9"><path d="m559 147 8-4 8 5m5-9 8-3 7 4m-65-3 6-4 6 4"/></g>
          {/* A decorative branch, not a page-sized floral photo. */}
          <g stroke="#44232E" strokeLinecap="round" strokeLinejoin="round" fill="none">
            <path d="M794-17C759 11 726 9 685 17s-68 27-101 45c-40 21-70 36-120 42" strokeWidth="5.5"/>
            <path d="M686 17c-11 17-16 39-34 57s-43 26-58 46M616 40c-8-23-27-33-42-42M575 61c-10-9-30-11-49-4M730 12c-5 23-3 39-18 64M519 87c-19-16-35-14-51-14" strokeWidth="2.8"/>
            <path d="M655 69c-22 1-34-8-46-16M611 98c4 18-5 28-17 41M748 27c-11-10-18-11-29-13" strokeWidth="1.8"/>
          </g>
          {/* Sakura blossoms with five separate petals and fine central dots. */}
          {flowers.map(([x,y,s,angle],i)=>(
            <g key={i} transform={`translate(${x} ${y}) rotate(${angle}) scale(${s})`}>
              {[0,72,144,216,288].map(a=><ellipse key={a} cx="0" cy="-7.8" rx="5.3" ry="8.8" transform={`rotate(${a})`} fill={i%3===0?'#EF9BA9':'#E78096'} opacity=".83"/>)}
              <circle r="3.2" fill="#8D2438"/>
              <circle r="1.3" fill="#FCE4D8"/>
            </g>
          ))}
          {petals.map(([x,y,angle],i)=><path key={i} d="M-9 0Q1-14 10 0Q1 10-9 0Z" transform={`translate(${x} ${y}) rotate(${angle})`} fill="#DD6179" opacity={i%2?.54:.72}/>)}
          {/* Seigaiha wave pattern on the bottom edge. */}
          <rect x="180" y="319" width="600" height="36" fill="url(#kairos-seigaiha)"/>
        </g>
      </svg>
    </div>
  );
}
