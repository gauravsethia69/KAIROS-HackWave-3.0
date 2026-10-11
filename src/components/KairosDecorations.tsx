import './kairos-decorations.css';

// Adapted from the isolated Lovable KAIROS decorative-components project.
// These are display-only SVG components: no state, libraries or event handlers.
function Blossom({ x, y, scale = 1, angle = 0 }: { x: number; y: number; scale?: number; angle?: number }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${angle}) scale(${scale})`} className="kairos-deco-sakura__flower">
      {[0, 72, 144, 216, 288].map(rotation => (
        <path key={rotation} transform={`rotate(${rotation})`}
          d="M0 1 C-3 -1 -6 -5 -4.5 -8.2 C-3.5 -10.3 -1.6 -10.8 0 -9.2 C1.6 -10.8 3.5 -10.3 4.5 -8.2 C6 -5 3 -1 0 1Z" />
      ))}
      <g className="kairos-deco-sakura__detail">
        <path d="M0 0L-1.2 -4 M0 0L3.4 -1.4 M0 0L2.2 3 M0 0L-2.2 3 M0 0L-3.4 -1.4" />
        <path d="M-1.9 -4h1.4 M3 -2l.9 1.2 M1.7 3.5l1.1 -.8 M-2.8 2.6l1.1 .8 M-4 -1l.8 -1.1" />
      </g>
    </g>
  );
}

/** Subtle branches tucked into opposite corners of the authenticated sidebar. */
export function SidebarSakuraBranches() {
  return (
    <div className="kairos-deco-sakura" aria-hidden="true">
      <svg className="kairos-deco-sakura__upper" viewBox="0 0 190 210" fill="none" aria-hidden="true" focusable="false">
        <g className="kairos-deco-sakura__wood">
          <path strokeWidth="2.8" d="M193 4C170 25 170 54 151 76C134 96 110 110 94 144" />
          <path strokeWidth="1.7" d="M177 30C159 34 137 35 115 53L83 73 M151 76C150 96 154 113 146 132 M125 108C102 103 80 106 58 120" />
          <path strokeWidth=".9" d="M139 39L132 19 M115 53L112 33 M100 62L78 57 M153 105L168 98 M106 126L112 150 M80 110L70 96 M62 118L43 114 M95 142L80 154" />
        </g>
        <Blossom x={113} y={43} scale={.85} angle={18}/>
        <Blossom x={91} y={64} scale={1} angle={-12}/>
        <Blossom x={75} y={77} scale={.66} angle={24}/>
        <Blossom x={130} y={22} scale={.57} angle={10}/>
        <Blossom x={69} y={104} scale={.8} angle={35}/>
        <Blossom x={52} y={118} scale={.95} angle={-14}/>
        <Blossom x={83} y={130} scale={.72} angle={8}/>
        <path className="kairos-deco-sakura__flower" d="M144 131C138 123 146 119 148 126C152 131 147 136 144 131Z M79 151C73 144 79 141 82 147C86 151 82 156 79 151Z"/>
      </svg>
      <svg className="kairos-deco-sakura__lower" viewBox="0 0 190 210" fill="none" aria-hidden="true" focusable="false">
        <g className="kairos-deco-sakura__wood">
          <path strokeWidth="2.6" d="M-4 210C18 190 25 160 44 139C62 119 78 107 89 81" />
          <path strokeWidth="1.5" d="M22 174C45 176 63 166 83 152L117 134 M44 139C43 119 39 106 48 87 M67 113C88 118 108 111 126 96" />
          <path strokeWidth=".85" d="M59 166L66 187 M83 152L87 173 M103 143L121 150 M42 110L27 102 M81 95L73 78 M107 108L117 119 M126 96L139 93" />
        </g>
        <Blossom x={88} y={158} scale={.83} angle={25}/>
        <Blossom x={109} y={141} scale={.95} angle={-8}/>
        <Blossom x={124} y={133} scale={.64} angle={16}/>
        <Blossom x={66} y={182} scale={.55} angle={-10}/>
        <Blossom x={118} y={104} scale={.8} angle={20}/>
        <Blossom x={133} y={91} scale={.7} angle={-25}/>
        <path className="kairos-deco-sakura__flower" d="M47 88C41 81 49 77 51 83C55 89 49 94 47 88Z M87 81C81 73 88 71 90 77C94 82 89 86 87 81Z"/>
      </svg>
    </div>
  );
}

/** Single, solid blood-red circle replacing the old top-right decorative sun. */
export function BloodRedSun() {
  return (
    <svg className="kairos-deco-sun" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <circle cx="50" cy="50" r="50" fill="currentColor"/>
    </svg>
  );
}
