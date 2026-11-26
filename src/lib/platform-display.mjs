const topics = {
  'topic-001': ['Energy policy', [
    'Links clean energy, infrastructure and wider public investment to jobs and economic opportunity.',
    'Emphasizes domestic energy supply, markets and deregulation, alongside some conservation and renewable measures.',
    'Supports green transition, public investment and democratic economic control alongside working-class organizing.',
  ]],
  'topic-002': ['Housing & community support', [
    'Supports public investment in housing, education, health and underserved communities.',
    'Supports safety-net providers, local partnerships, veterans and families facing need.',
    'Supports expanded social programs, housing and infrastructure to meet working-class and marginalized communities’ needs.',
  ]],
  'topic-003': ['Labor & unions', [
    'Supports unions, collective bargaining, organizing rights, higher wages and workplace protections.',
    'Emphasizes right-to-work, secret-ballot union elections, worker choice and selected workplace protections.',
    'Supports rank-and-file unionism, strikes, solidarity and worker power across workplaces and movements.',
  ]],
  'topic-004': ['Growth & economic models', [
    'Connects prosperity to public investment, infrastructure, manufacturing, education and inclusion.',
    'Connects growth to markets, trade, lower taxes, deregulation and entrepreneurship.',
    'Critiques capitalist growth while supporting democratic planning, redistribution and socialist alternatives.',
  ]],
  'topic-005': ['Voting & representation', [
    'Supports ballot access, voting-rights enforcement, campaign-finance reform and democratic accountability.',
    'Supports voter identification, citizenship checks, paper ballots, state authority and selected constitutional safeguards.',
    'Supports expanded voting rights, proportional representation and limits on corporate influence over democracy.',
  ]],
  'topic-006': ['America’s global role', [
    'Portrays American strength through democratic values, alliances, diplomacy and shared prosperity.',
    'Portrays America as an exceptional leader backed by military strength, economic power, alliances and resolve.',
    'Criticizes U.S. empire and intervention while supporting international solidarity and self-determination.',
  ]],
  'topic-007': ['Public commitments', [
    'Commits to opportunity, nondiscrimination, social insurance, community strength and public safety.',
    'Commits to families, efficient government, national strength, social insurance and economic stability.',
    'Supports economic democratization, public investment, expanded rights, working-class organization and reduced military spending.',
  ]],
  'topic-009': ['Diplomacy & cooperation', [
    'Favors alliances, diplomacy, negotiated agreements and international cooperation across policy areas.',
    'Combines alliances and trade agreements with sovereignty, enforcement, competition and reservations about some international institutions.',
    'Supports cooperation while opposing militarism, coercive intervention and trade rules viewed as subordinating workers or poorer nations.',
  ]],
  'topic-010': ['Policing & criminal justice', [
    'Combines policing and community safety with sentencing reform, rehabilitation and civil-rights enforcement.',
    'Emphasizes police support, prosecution, victims and punishment, with some rehabilitation and reentry commitments.',
    'Criticizes punitive policing and incarceration while supporting decarceration, abolitionist organizing and material alternatives.',
  ]],
  'topic-011': ['Tax policy', [
    'Pairs lower-income tax relief and credits with corporate enforcement and greater contributions from wealthy households.',
    'Favors lower and simpler taxes for families, businesses, investment, estates and savings.',
    'Advocates progressive taxes on corporations, wealth and high incomes to fund social programs and reduce concentrated power.',
  ]],
  'topic-012': ['Education', [
    'Emphasizes public investment, teachers, broad access, accountability and affordable college pathways.',
    'Emphasizes parental choice, local control, standards, charters, vouchers and homeschooling.',
    'Treats education as a public good, supporting universal access, public funding and democratic control.',
  ]],
  'topic-013': ['Reproductive & gender rights', [
    'Supports reproductive autonomy, abortion access, gender and LGBTQ equality, and family protections.',
    'Emphasizes fetal life, abortion restrictions, conscience protections, adoption and traditional marriage or sex classifications.',
    'Connects reproductive freedom and gender and sexual liberation with healthcare, childcare and economic rights.',
  ]],
  'topic-014': ['Military & war policy', [
    'Combines military readiness and counterterrorism with diplomacy, oversight and ending particular wars.',
    'Emphasizes military strength, defense systems, counterterrorism and preserving options to use force.',
    'Opposes war and expansive military spending while supporting diplomacy, demilitarization and antiwar organizing.',
  ]],
  'topic-015': ['Critiques across policy areas', [
    'Criticizes Republican administrations across policy areas, sometimes pairing objections with alternative commitments.',
    'Criticizes Democratic administrations, federal expansion and selected domestic, international and security policies.',
    'Criticizes both major parties, capitalism, militarism and austerity while advancing socialist or movement-based alternatives.',
  ]],
  'topic-016': ['Presidential records', [
    'Praises Democratic presidential records and commitments while criticizing Republican administrations.',
    'Praises Republican presidential leadership while criticizing Democratic administrations across policy areas.',
    'Assesses presidential and government records through socialist critiques of war, austerity, corporate power and Democratic Party limitations.',
  ]],
  'topic-018': ['Health care', [
    'Seeks broad affordable coverage, stronger Medicare and Medicaid, lower costs and reduced disparities.',
    'Supports affordable access through choice, competition, private provision and changes to public programs.',
    'Treats healthcare as a right, favoring Medicare for All, comprehensive single-payer coverage and care without point-of-use charges.',
  ]],
  'topic-019': ['Poverty & housing insecurity', [
    'Describes poverty, job loss, housing costs, racial wealth gaps and health costs across election periods.',
    'Describes poverty, inflation, unemployment, uninsured families and fiscal distress, sometimes assigning partisan blame.',
    'Connects hardship to low wages, austerity, privatization, capitalism and burdens on workers and marginalized communities.',
  ]],
  'topic-020': ['Power & social conflict', [
    'Describes threats from authoritarianism, discrimination, anti-worker conduct and institutions that undermine rights or democracy.',
    'Describes threats from foreign repression, crime, government overreach and institutions portrayed as weakening freedom or order.',
    'Links oppression and conflict to capitalism, racism, austerity, policing, borders, militarism and divisions among working people.',
  ]],
  'topic-021': ['Immigration', [
    'Combines citizenship pathways, family reunification and immigrant protections with border security, screening and enforcement.',
    'Welcomes legal immigration while emphasizing border control, screening, detention or removal and lawful citizenship processes.',
    'Supports citizenship, asylum, migrant labor rights and free movement while opposing punitive immigration controls.',
  ]],
  'topic-022': ['Israel & Palestine', [
    'Combines Israeli security with Palestinian statehood and diplomacy; 2024 examples add ceasefire and Gaza reconstruction language.',
    'Emphasizes Israeli security and regional peace, alongside recurring conditional support for Palestinian statehood.',
    'Stresses Palestinian sovereignty and ending occupation; some earlier samples endorse two-state peace and Israeli civilian security.',
  ]],
  'topic-024': ['Views of the Trump record', [
    'Criticizes Trump’s record across domestic and foreign policy and democratic norms.',
    'Chiefly in 2024 samples, praises Trump’s record and promises renewed implementation.',
    'Criticizes Trump’s record while describing movement growth and opposition during his presidency.',
  ]],
};

const caucuses = {
  'topic-005': 'Building a mass organization',
  'topic-011': 'Campaigns & revolutionary openings',
  'topic-002': 'Capitalism & exploitation',
  'topic-006': 'Class struggle & solidarity',
  'topic-010': 'DSA strategy & internal debate',
  'topic-003': 'Democracy & political power',
  'topic-009': 'Ecology & economic change',
  'topic-004': 'Labor & working-class power',
  'topic-012': 'Tendencies & ideological identity',
  'topic-008': 'Oppression & anti-imperialism',
  'topic-007': 'Traditions & organizing approaches',
  'topic-001': 'Socialist & democratic aims',
};

export function issueLabel(id) {
  if (!topics[id]) throw new Error(`Missing issue display label: ${id}`);
  return topics[id][0];
}

export function positionReadout(id, group) {
  const index = ['democratic', 'republican', 'dsa'].indexOf(group);
  if (!topics[id] || index < 0) throw new Error(`Missing position readout: ${id}/${group}`);
  return topics[id][1][index];
}

export function caucusLabel(id) {
  if (!caucuses[id]) throw new Error(`Missing caucus display label: ${id}`);
  return caucuses[id];
}
