/** Pass 12H: deterministic high-confidence route selector for existing KAIROS surfaces.
 * This is NOT an authorization decision, an LLM classifier or a SQL planner.
 * Unknown or mixed requests stay with the already-authorized enterprise engine.
 * No network calls, no extra Groq tokens, no changes to stored records.
 */
export type KairosRoute = 'company_guide' | 'general_advice' | 'enterprise';

function normalized(input: string): string {
  return input.normalize('NFKC').toLowerCase()
    .replace(/[’‘`]/g, "'")
    .replace(/\b(?:i'm|im)\b/g, 'i am')
    .replace(/\b(?:what's|whats)\b/g, 'what is')
    .replace(/\b(?:we're|were)\b/g, 'we are')
    .replace(/\b(?:don't|dont)\b/g, 'do not')
    .replace(/[^a-z0-9&\s'-]+/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

/** Live, personal, measured, or action requests must not be diverted to documents or generic advice.
 * Consciously over-block rather than fabricate organizational facts.
 */
const operation = /\b(?:show|list|find|fetch|query|investigate|review|compare|dashboard|report|chart|graph|analy[sz]e|audit|track|monitor|schedule|book|create|assign|update|delete|cancel|reschedule|move|edit)\b|\b(?:my|our)\s+(?:tasks?|assignments?|calendar|schedule|meetings?|projects?|clients?|manager|department|workload|capacity|actual|recorded|current|last|previous|historical|specific|metrics|numbers|statistics|data)\b|\b(?:who\s+(?:owns|is\s+responsible|handles|is\s+assigned)|what\s+(?:am\s+i\s+assigned|is\s+my\s+team)|which\s+(?:employees?|tasks?|projects?|clients?|team\s+am\s+i)|overdue|overloaded|blocked\s+tasks?|due\s+dates?|live\s+data|database|last\s+(?:week|month|quarter|year)|this\s+(?:week|month|quarter)|next\s+week|yesterday|tomorrow)\b/i;

// Suppress free-form AI if named third-party records or their performance are involved.
const identifiableRecords = /\b(?:orbitpay|northstar|atlas\s+media|acme\s+corp|nova\s+studio)\b/i;

// Several independent ways to express a general company-knowledge request.
const onboarding = /\b(?:i\s+(?:am|was)\s+(?:a\s+)?new\s+(?:employee|hire|joiner|starter|here|at\s+(?:soryu|this\s+(?:company|place|organization))|to\s+(?:soryu|the\s+(?:team|company|organization)))|new\s+(?:here|hire|joiner|starter|employee|to\s+(?:soryu|the\s+(?:team|company|organization)))|just\s+(?:joined|started|hired|onboarded)|first\s+day|onboard(?:ing)?|getting\s+started|recently\s+joined|starting\s+(?:here|at\s+soryu))\b/i;
const organizationKnowledge = /\b(?:tell\s+me\s+about\s+(?:soryu|the\s+company|our\s+company)|(?:explain|describe|understand|learn\s+about)\s+(?:soryu|our\s+company|the\s+company|company\s+structure|how\s+the\s+company\s+works)|(?:company|organization)\s+(?:guide|handbook|structure|overview)|how\s+(?:do|does)\s+(?:things?|everything|stuff|the\s+company|this\s+company|soryu|work)\s+(?:work|operate|run)\b|how\s+(?:things?|everything|the|this|our)\s+(?:work|works|operate|operates|company\s+works)\b|how\s+does\s+(?:everything|this\s+place|the\s+organization)\s+work\b|how\s+(?:is|are)\s+(?:soryu|this\s+company|the\s+organization)\s+(?:organized|structured)|what\s+(?:does|do)\s+(?:engineering|support|sales|operations|product|customer\s+success|data\s+(?:and|&)\s+analytics)\s+(?:do|handle))\b/i;
const locationKnowledge = /\b(?:here|around\s+here|at\s+soryu|in\s+this\s+(?:company|organization|place))\b/i;
const getOriented = /\b(?:how\s+do\s+i\s+(?:get\s+started|settle\s+in|find\s+my\s+way)|where\s+(?:should|do)\s+i\s+start|help\s+me\s+(?:get\s+oriented|understand\s+(?:how\s+things?\s+work|the\s+company)))\b/i;
const productReference = /\b(?:what\s+(?:is|does)|explain|tell\s+me\s+about|describe|overview\s+of)\s+soryu\s+(?:cloudops|guard|flow|insight)\b/i;

const adviceRequest = /^(?:how\s+(?:can|could|should|do|would)\s+(?:(?:we|i|our\s+team|a\s+company|businesses|soryu(?:\s+systems)?)\s+)?|how\s+to\s+|what\s+(?:can|should|could)\s+we\s+do\s+(?:to|about)\s+|what\s+strategies\s+(?:can|could)\s+(?:help\s+)?|what\s+are\s+(?:some\s+)?(?:ways|strategies|tips|ideas|best\s+practices)\s+(?:to|for)\s+|(?:give|suggest|recommend|share)\s+(?:me\s+|us\s+)?(?:some\s+)?(?:ways|strategies|tips|ideas|recommendations)\s+(?:to|for|on)\s+|(?:ways|strategies|tips|ideas|recommendations)\s+(?:to|for|on)\s+|(?:help\s+(?:us|me)\s+(?:to|with)\s+|any\s+(?:ideas|tips|strategies)\s+(?:for|to)\s+|best\s+way\s+to\s+|i\s+need\s+(?:some\s+)?(?:advice|tips|ideas)\s+(?:on|for|to)\s+|(?:can|could)\s+you\s+(?:suggest|recommend|help\s+(?:me|us))\s+))/i;
const adviceTopic = /\b(?:sales|selling|sell|revenue|conversion|leads?|marketing|churn|retention|customers?|clients?|customer\s+service|communication|teamwork|collaboration|productivity|efficient|efficiency|meetings?|employee\s+(?:engagement|motivation|morale)|business\s+growth|onboarding|project\s+management|customer\s+acquisition|brand\s+awareness|support\s+quality|feedback|product\s+adoption|enterprise\s+sales|team\s+performance)\b/i;
// Require an improvement/strategy sense; don't spend AI on pure how-to instructions
// such as "how to schedule a meeting?" or "how do I find my manager?".
const improvement = /\b(?:improv\w*|increase|grow|boost|expand|raise|better|reduce|lower|cut|decrease|minimi[sz]e|prevent|retain|attract|engage|convert|win|more|effective|efficient|optimi[sz]e|enhance|strengthen|drive|develop|scale|handle|address|solve)\b/i;
const actionHelp = /\b(?:how\s+to\s+schedule|how\s+to\s+book|how\s+to\s+create|how\s+to\s+update|how\s+to\s+find|how\s+to\s+view)\b/i;

export function routeKairosQuestion(input: string): KairosRoute {
  if (input.length > 650 || input.length < 8) return 'enterprise';
  const q = normalized(input);
  if (q.length < 8 || operation.test(q) || identifiableRecords.test(q)) return 'enterprise';
  if (adviceRequest.test(q) && adviceTopic.test(q) && improvement.test(q) && !actionHelp.test(q)) {
    return 'general_advice';
  }
  if (productReference.test(q) || getOriented.test(q) || organizationKnowledge.test(q) ||
      (onboarding.test(q) && (locationKnowledge.test(q) || /\b(?:employee|hire|joiner|starter|onboard|joined|first\s+day|getting\s+started)\b/i.test(q)))) {
    return 'company_guide';
  }
  return 'enterprise'; // Abstain instead of guessing an answer or reclassifying an operation.
}
