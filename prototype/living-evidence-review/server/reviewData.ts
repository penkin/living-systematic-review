import type { RecordSeed } from "./reviewEngine";

const score = (relevance: number, lmic: number, equity: number, design: number, policy: number, novelty: number, uncertainty: number) => ({ relevance, lmic, equity, design, policy, novelty, uncertainty });

export const recordSeeds: RecordSeed[] = [
  {
    id: "SYN-001", title: "Ambient heat exposure and preterm birth in a Nairobi maternity cohort",
    summary: "2,340 pregnancies in three public maternity units in Nairobi, 2021–2024. Highest temperature quintile in the final gestational month was associated with preterm birth, concentrated among women in informal settlements.",
    year: 2026, language: "English", country: "Kenya", region: "East Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Cohort", population: "Pregnant people attending public maternity units", exposure: "Ambient heat", outcomeText: "Preterm birth", mappedOutcome: "O5", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 2, 1, 2, 1, 3), certainty: "Very low", existingStudies: 3, progressPlus: ["Place of residence", "Socioeconomic status", "Pregnancy"], policyArea: "Maternal health and heat protection", publicationStatus: "published",
  },
  {
    id: "SYN-002", title: "Acute kidney injury among outdoor market traders during hot season in Kumasi",
    summary: "Prospective study of 180 outdoor market traders. Serum creatinine was measured at the start and end of the hot season; 16% met criteria for incident kidney injury. Water access modified the association.",
    year: 2026, language: "English", country: "Ghana", region: "West Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Cohort", population: "Outdoor market traders", exposure: "Hot season occupational heat", outcomeText: "Incident kidney injury", mappedOutcome: "O6", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 2, 1, 2, 1, 3), certainty: "Very low", existingStudies: 2, progressPlus: ["Occupation", "Informal work", "Water access"], policyArea: "Occupational heat protection", publicationStatus: "published",
  },
  {
    id: "SYN-003", title: "Heat stress and milk yield in smallholder dairy herds in central Kenya",
    summary: "Temperature-humidity index was recorded at 42 smallholder dairy farms for 18 months. Higher index values were associated with declining milk yield.",
    year: 2025, language: "English", country: "Kenya", region: "East Africa", setting: "Rural", recordType: "Journal article", studyDesign: "Cohort", population: "Smallholder dairy herds", exposure: "Heat stress", outcomeText: "Milk yield", relevanceLabel: "Not relevant", scopeIssue: "Animal/agricultural study; no human health outcome addresses the review question.", scopeStatus: "out_of_scope", signalEligible: false, scores: score(0, 0, 0, 1, 1, 0, 0), publicationStatus: "published",
  },
  {
    id: "SYN-004", title: "Hot days and primary school absenteeism in urban Malawi",
    summary: "Attendance registers from 22 primary schools in Blantyre were linked to temperature across three academic years. Absenteeism rose above the 90th temperature percentile.",
    year: 2026, language: "English", country: "Malawi", region: "Southern Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Cohort", population: "Primary school pupils", exposure: "Hot days", outcomeText: "School absenteeism", potentialNewOutcome: "Education attendance", relevanceLabel: "Partial", scopeIssue: "Heat-related school absenteeism is outside the current H3 outcome map.", scopeStatus: "scope_question", signalEligible: false, scores: score(1, 2, 1, 1, 1, 1, 0), progressPlus: ["Age", "Place of residence"], policyArea: "Education continuity", publicationStatus: "published",
  },
  {
    id: "SYN-005", title: "Heatwaves and all-cause mortality in Johannesburg: a 15-year time-series analysis",
    summary: "Daily all-cause mortality counts for Johannesburg from 2009 to 2024 were analysed using distributed lag non-linear models. Heatwave days were associated with elevated mortality.",
    year: 2026, language: "English", country: "South Africa", region: "Southern Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Time-series", population: "Johannesburg population", exposure: "Heatwaves", outcomeText: "All-cause mortality", mappedOutcome: "O1", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 0, 1, 1, 1, 1, 1), certainty: "Moderate", existingStudies: 14, progressPlus: ["Place of residence", "Age"], policyArea: "Heat-health planning", publicationStatus: "published",
  },
  {
    id: "SYN-006", title: "Fine particulate matter and paediatric respiratory admissions in Nairobi",
    summary: "Paediatric respiratory admissions were associated with daily PM2.5. Models adjusted for humidity and ambient temperature.",
    year: 2026, language: "English", country: "Kenya", region: "East Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Time-series", population: "Children admitted to referral hospitals", exposure: "PM2.5; heat only an adjustment variable", outcomeText: "Respiratory admissions", relevanceLabel: "Not relevant", scopeIssue: "PM2.5 is the exposure; temperature is only an adjustment variable.", scopeStatus: "out_of_scope", signalEligible: false, scores: score(0, 2, 1, 1, 1, 1, 0), publicationStatus: "published",
  },
  {
    id: "SYN-007", title: "Environmental determinants of hospital admissions in three coastal cities",
    summary: "2.1 million admission records from Dar es Salaam, Maputo and Durban were analysed. Heat-attributable admissions were highest in cardiovascular and renal categories.",
    year: 2026, language: "English", country: "Multi-country, Africa", region: "Multi-region Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Case-crossover", population: "Hospital patients in three coastal cities", exposure: "Ambient temperature and humidity", outcomeText: "Heat-attributable hospital admissions; cardiovascular and renal categories", possibleOutcomes: ["O2 — Heat-related emergency-department attendance", "O6 — Renal/kidney injury"], relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 2, 1, 2, 1, 3), certainty: "Very low", existingStudies: 2, progressPlus: ["Place of residence", "Health service access"], policyArea: "Hospital preparedness", publicationStatus: "published",
  },
  {
    id: "SYN-008", title: "Projected heat-related mortality in 47 African cities to 2100 under alternative emissions pathways",
    summary: "Climate projections and published exposure-response functions were combined to project heat-attributable deaths. No new empirical exposure data were collected.",
    year: 2026, language: "English", country: "Africa", region: "Multi-region Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Modelling", population: "47 African cities", exposure: "Projected future heat", outcomeText: "Projected mortality", relevanceLabel: "Partial", scopeIssue: "Modelling study adds projections but collects no new empirical exposure data.", scopeStatus: "context", signalEligible: false, scores: score(1, 2, 1, 1, 2, 1, 0), policyArea: "Climate adaptation planning", publicationStatus: "published",
  },
  {
    id: "SYN-009", title: "Physiological heat strain among construction workers in Dar es Salaam",
    summary: "Core temperature and heart rate were monitored in 96 construction workers across 14 sites. 41% exceeded physiological strain thresholds.",
    year: 2026, language: "English", country: "Tanzania", region: "East Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Cross-sectional", population: "Construction workers", exposure: "Occupational heat", outcomeText: "Physiological heat strain", mappedOutcome: "O4", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 2, 1, 2, 1, 2), certainty: "Low", existingStudies: 5, progressPlus: ["Occupation", "Work conditions"], policyArea: "Occupational rest and heat protection", publicationStatus: "published",
  },
  {
    id: "SYN-010", title: "Ambient temperature and assault-related emergency presentations in Gauteng",
    summary: "Assault-related emergency presentations across nine Gauteng facilities increased on hotter days, especially in the late afternoon and evening.",
    year: 2026, language: "English", country: "South Africa", region: "Southern Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Time-series", population: "Emergency department attendees", exposure: "Ambient temperature", outcomeText: "Assault-related presentations", potentialNewOutcome: "Interpersonal violence", relevanceLabel: "Partial", scopeIssue: "Heat-related interpersonal violence is not currently an H3 outcome.", scopeStatus: "scope_question", signalEligible: false, scores: score(1, 0, 1, 1, 1, 1, 0), policyArea: "Emergency services", publicationStatus: "published",
  },
  {
    id: "SYN-011", title: "Thermal comfort and occupant satisfaction in naturally ventilated office buildings in Cairo",
    summary: "Indoor temperature, humidity and air velocity were measured in 12 naturally ventilated office buildings with comfort surveys. Recommendations for design standards are provided.",
    year: 2026, language: "English", country: "Egypt", region: "North Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Cross-sectional", population: "Office occupants", exposure: "Indoor temperature", outcomeText: "Thermal comfort and occupant satisfaction", relevanceLabel: "Partial", scopeIssue: "Thermal comfort informs building policy but is not a current health outcome.", scopeStatus: "context", signalEligible: false, scores: score(1, 0, 1, 1, 2, 1, 0), policyArea: "Building design standards", publicationStatus: "published",
  },
  {
    id: "SYN-012", title: "RETRACTED: Ambient temperature and stroke admissions in Lagos, 2018–2023",
    summary: "Retracted after an institutional investigation identified irregularities in the admission dataset. The original abstract reported an association between temperature and stroke admissions.",
    year: 2026, language: "English", country: "Nigeria", region: "West Africa", setting: "Urban", recordType: "Journal article (retracted)", studyDesign: "Time-series", population: "Stroke admissions", exposure: "Ambient temperature", outcomeText: "Ischaemic stroke admissions", relevanceLabel: "Direct", scopeIssue: "Retraction and dataset irregularities prevent a reliable signal decision.", scopeStatus: "signal", signalEligible: false, scores: score(3, 2, 1, 1, 1, 1, 0), publicationStatus: "retracted",
  },
  {
    id: "SYN-013", title: "Ten-year evaluation of the Ahmedabad Heat Action Plan: mortality impact and implementation lessons",
    summary: "A difference-in-differences evaluation estimated avoided deaths after a municipal heat action plan and described implementation barriers and warning-threshold adaptation.",
    year: 2026, language: "English", country: "India", region: "South Asia", setting: "Urban", recordType: "Journal article", studyDesign: "Non-randomised", population: "Ahmedabad population", exposure: "Heat action plan", outcomeText: "Mortality and implementation", relevanceLabel: "Partial", scopeIssue: "Ahmedabad evidence is informative but outside the current African setting scope.", scopeStatus: "out_of_scope", signalEligible: false, scores: score(2, 0, 0, 1, 2, 1, 0), policyArea: "Heat action plans", publicationStatus: "published",
  },
  {
    id: "SYN-014", title: "Cool roof coatings and indoor heat exposure in Cape Town informal settlements: a cluster-randomised trial",
    summary: "Ninety-six dwelling clusters were randomised to reflective roof coating or usual conditions. Coated dwellings had lower indoor peak temperatures and fewer heat-disturbed nights.",
    year: 2026, language: "English", country: "South Africa", region: "Southern Africa", setting: "Urban informal settlements", recordType: "Journal article", studyDesign: "RCT", population: "Residents of informal settlements", exposure: "Indoor heat", outcomeText: "Cooling intervention and heat exposure", mappedOutcome: "O7", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 0, 2, 2, 2, 1, 3), certainty: "Very low", existingStudies: 2, newInterventionClass: true, progressPlus: ["Place of residence", "Socioeconomic status", "Informal settlement"], policyArea: "Housing adaptation", duplicateGroupId: "CR-CPT-001", publicationStatus: "published",
  },
  {
    id: "SYN-015", title: "Daily temperature and cardiovascular mortality in Alexandria",
    summary: "Cardiovascular mortality records from 2012 to 2024 were analysed against daily temperature. Risk increased above the 85th temperature percentile, especially among adults over 65.",
    year: 2026, language: "English", country: "Egypt", region: "North Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Time-series", population: "Adults, especially older adults", exposure: "Ambient temperature", outcomeText: "Cardiovascular mortality", mappedOutcome: "O3", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 0, 1, 1, 1, 1, 2), certainty: "Low", existingStudies: 6, progressPlus: ["Age"], policyArea: "Heat-health planning", publicationStatus: "published",
  },
  {
    id: "SYN-016", title: "Heat exposure and adverse birth outcomes in Kampala: protocol for a prospective cohort study",
    summary: "Protocol for a planned cohort of 4,000 pregnancies linking personal heat exposure to preterm birth and low birthweight. No results are reported.",
    year: 2026, language: "English", country: "Uganda", region: "East Africa", setting: "Urban", recordType: "Study protocol", studyDesign: "Cohort", population: "Pregnant people", exposure: "Personal heat exposure", outcomeText: "Preterm birth and low birthweight", mappedOutcome: "O5", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: false, scores: score(3, 2, 2, 0, 2, 1, 3), certainty: "Very low", existingStudies: 3, progressPlus: ["Pregnancy"], policyArea: "Maternal health", publicationStatus: "protocol",
  },
  {
    id: "SYN-017", title: "How households cope with extreme heat in Nairobi informal settlements: a qualitative study",
    summary: "Interviews and focus groups described sleeping outdoors, wetting bedding, rescheduling work, and barriers involving cost and landlord permission.",
    year: 2026, language: "English", country: "Kenya", region: "East Africa", setting: "Urban informal settlements", recordType: "Journal article", studyDesign: "Qualitative", population: "Residents of informal settlements", exposure: "Extreme heat", outcomeText: "Household coping and adaptation barriers", relevanceLabel: "Partial", scopeIssue: "Qualitative coping evidence informs adaptation barriers but reports no mapped health outcome.", scopeStatus: "context", signalEligible: false, scores: score(1, 2, 2, 1, 2, 1, 0), progressPlus: ["Place of residence", "Socioeconomic status"], policyArea: "Housing adaptation", publicationStatus: "published",
  },
  {
    id: "SYN-018", title: "Emergency department attendance during heat events in Durban",
    summary: "Attendance records from three Durban emergency departments across six hot seasons were linked to temperature. Attendance rose modestly, driven by dehydration and cardiovascular presentations.",
    year: 2026, language: "English", country: "South Africa", region: "Southern Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Time-series", population: "Emergency department attendees", exposure: "Heat events", outcomeText: "Emergency department attendance", mappedOutcome: "O2", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 0, 1, 1, 1, 1, 1), certainty: "Moderate", existingStudies: 9, progressPlus: ["Health service access"], policyArea: "Emergency preparedness", publicationStatus: "published",
  },
  {
    id: "SYN-019", title: "PREPRINT: Heatwaves and all-cause mortality in Johannesburg, 2009–2024",
    summary: "Non-peer-reviewed preprint using the same Johannesburg period and methods as SYN-005. Results are consistent with the journal analysis.",
    year: 2026, language: "English", country: "South Africa", region: "Southern Africa", setting: "Urban", recordType: "Preprint", studyDesign: "Time-series", population: "Johannesburg population", exposure: "Heatwaves", outcomeText: "All-cause mortality", mappedOutcome: "O1", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: false, scores: score(3, 0, 1, 1, 1, 0, 1), certainty: "Moderate", existingStudies: 14, duplicateGroupId: "JHB-MORT-001", scopeIssue: "Preprint duplicates SYN-005 and must not create a second independent signal.", publicationStatus: "preprint_duplicate",
  },
  {
    id: "SYN-020", title: "Ambient temperature and all-cause mortality in Addis Ababa",
    summary: "Mortality registration data from Addis Ababa, 2014–2024, were analysed against daily temperature. Elevated mortality was observed at high temperatures.",
    year: 2026, language: "English", country: "Ethiopia", region: "East Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Time-series", population: "Addis Ababa population", exposure: "Ambient temperature", outcomeText: "All-cause mortality", mappedOutcome: "O1", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 1, 1, 1, 1, 1), certainty: "Moderate", existingStudies: 14, progressPlus: ["Place of residence"], policyArea: "Heat-health planning", publicationStatus: "published",
  },
  {
    id: "SYN-021", title: "Evaluation of a municipal heat early warning system in Ouagadougou",
    summary: "SMS alerts, radio broadcasts and community health worker activation were evaluated across two hot seasons using interrupted time series. Clinic presentations declined after implementation.",
    year: 2026, language: "English", country: "Burkina Faso", region: "West Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Non-randomised", population: "Residents and heat-related clinic attendees", exposure: "Heat early-warning system", outcomeText: "Early-warning system performance and clinic presentations", mappedOutcome: "O8", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 2, 1, 2, 1, 3), certainty: "Very low", existingStudies: 1, progressPlus: ["Place of residence", "Health service access"], policyArea: "Heat early-warning systems", publicationStatus: "published",
  },
  {
    id: "SYN-022", title: "Adverse events associated with community cooling centre use during heat events in eThekwini",
    summary: "Incident review across 14 cooling centres identified gastrointestinal illness linked to shared water dispensers and falls on wet flooring.",
    year: 2026, language: "English", country: "South Africa", region: "Southern Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Non-randomised", population: "Cooling centre attendees, including older people", exposure: "Cooling centre intervention", outcomeText: "Intervention-related adverse events", mappedOutcome: "O7", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 0, 2, 1, 2, 1, 3), certainty: "Very low", existingStudies: 2, harmReported: true, progressPlus: ["Age", "Health and safety"], policyArea: "Cooling centre safety", publicationStatus: "published",
  },
  {
    id: "SYN-023", title: "Vagues de chaleur et mortalite infantile a Dakar: une analyse de series temporelles",
    summary: "French-language time-series analysis of infant deaths in Dakar, 2015–2025. Hot days were associated with increased infant mortality, with no previous West African study identified.",
    year: 2026, language: "French", country: "Senegal", region: "West Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Time-series", population: "Infants in Dakar", exposure: "Heatwaves", outcomeText: "Infant mortality", mappedOutcome: "O1", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 2, 1, 2, 1, 1), certainty: "Moderate", existingStudies: 14, contextGap: "West African mortality evidence", progressPlus: ["Age", "Place of residence", "Language"], policyArea: "Heat-health planning", publicationStatus: "published",
  },
  {
    id: "SYN-024", title: "Wearable monitoring of heat strain among informal waste workers in Kigali",
    summary: "Thirty-eight informal waste workers wore chest-mounted sensors for ten hot-season working days. Sustained physiological strain was observed during afternoon collection rounds.",
    year: 2026, language: "English", country: "Rwanda", region: "East Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Cross-sectional", population: "Informal waste workers", exposure: "Occupational heat", outcomeText: "Physiological heat strain", mappedOutcome: "O4", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 2, 1, 2, 1, 2), certainty: "Low", existingStudies: 5, progressPlus: ["Occupation", "Informal work"], policyArea: "Occupational heat protection", publicationStatus: "published",
  },
  {
    id: "SYN-025", title: "Cold exposure and acute respiratory infection in highland Lesotho households",
    summary: "Lower indoor overnight temperature during winter was associated with acute respiratory infection in children under five.",
    year: 2026, language: "English", country: "Lesotho", region: "Southern Africa", setting: "Rural", recordType: "Journal article", studyDesign: "Cohort", population: "Children under five", exposure: "Cold exposure", outcomeText: "Acute respiratory infection", relevanceLabel: "Not relevant", scopeIssue: "Cold exposure is outside the review’s heat-exposure scope.", scopeStatus: "out_of_scope", signalEligible: false, scores: score(0, 0, 1, 1, 1, 1, 0), publicationStatus: "published",
  },
  {
    id: "SYN-026", title: "Heat exposure and mortality worldwide: an updated systematic review and meta-analysis",
    summary: "Systematic review of 214 studies reporting heat and mortality associations; African studies contributed 6% of included estimates.",
    year: 2026, language: "English", country: "Global", region: "Global", setting: "Mixed", recordType: "Systematic review", studyDesign: "SR", population: "Global studies", exposure: "Ambient heat", outcomeText: "Mortality", relevanceLabel: "Partial", scopeIssue: "Systematic review informs background but is not a new primary study for this signal update.", scopeStatus: "context", signalEligible: false, scores: score(1, 0, 1, 2, 2, 1, 0), policyArea: "Evidence synthesis", publicationStatus: "synthesis",
  },
  {
    id: "SYN-027", title: "Heat and health in African cities: time to move from evidence to action",
    summary: "Commentary argues African cities have a thin evidence base and calls for coordinated intervention trials.",
    year: 2026, language: "English", country: "Africa", region: "Multi-region Africa", setting: "Urban", recordType: "Commentary", studyDesign: "Other", population: "African cities", exposure: "Heat", outcomeText: "Evidence and intervention priorities", relevanceLabel: "Partial", scopeStatus: "context", signalEligible: false, scores: score(1, 2, 1, 0, 2, 1, 0), policyArea: "Research and intervention policy", publicationStatus: "commentary",
  },
  {
    id: "SYN-028", title: "Cool roof coatings in Cape Town informal settlements: secondary outcomes and cost analysis",
    summary: "Secondary outcomes from the Cape Town reflective roof-coating trial include sleep quality, clinic attendance and installation cost per dwelling.",
    year: 2026, language: "English", country: "South Africa", region: "Southern Africa", setting: "Urban informal settlements", recordType: "Journal article", studyDesign: "RCT", population: "Residents of informal settlements", exposure: "Indoor heat intervention", outcomeText: "Sleep quality, clinic attendance and intervention cost", mappedOutcome: "O7", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 0, 2, 2, 2, 1, 3), certainty: "Very low", existingStudies: 2, newInterventionClass: true, progressPlus: ["Place of residence", "Socioeconomic status"], policyArea: "Housing adaptation and implementation cost", duplicateGroupId: "CR-CPT-001", publicationStatus: "published",
  },
  {
    id: "SYN-029", title: "Ambient temperature and childhood diarrhoeal admissions in Maputo",
    summary: "Paediatric diarrhoeal admissions at two Maputo hospitals increased following elevated temperature, especially among children under two.",
    year: 2026, language: "English", country: "Mozambique", region: "Southern Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Time-series", population: "Children under two", exposure: "Ambient temperature", outcomeText: "Childhood diarrhoeal admissions", potentialNewOutcome: "Childhood diarrhoeal disease", relevanceLabel: "Partial", scopeIssue: "Childhood diarrhoeal admissions are not currently mapped to an H3 outcome.", scopeStatus: "scope_question", signalEligible: false, scores: score(1, 2, 2, 1, 2, 1, 0), progressPlus: ["Age", "Health service access"], policyArea: "Child health services", publicationStatus: "published",
  },
  {
    id: "SYN-030", title: "Urban green space access and physical activity among adults in Accra",
    summary: "A cross-sectional survey found higher physical activity among residents living near accessible green space. No heat exposure was reported.",
    year: 2026, language: "English", country: "Ghana", region: "West Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Cross-sectional", population: "Adults in Accra", exposure: "No heat exposure reported", outcomeText: "Physical activity", relevanceLabel: "Not relevant", scopeIssue: "No heat exposure or heat-related health outcome is reported.", scopeStatus: "out_of_scope", signalEligible: false, scores: score(0, 2, 1, 1, 1, 1, 0), publicationStatus: "published",
  },
  {
    id: "SYN-031", title: "Heat events and mental health service attendance in Lusaka [conference abstract]",
    summary: "Conference abstract reports apparently elevated mental-health service attendance during heat events, without full methods or effect estimates.",
    year: 2026, language: "English", country: "Zambia", region: "Southern Africa", setting: "Urban", recordType: "Conference abstract", studyDesign: "Other", population: "Mental-health service attendees", exposure: "Heat events", outcomeText: "Mental-health service attendance", mappedOutcome: "O9", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: false, scores: score(3, 2, 1, 0, 1, 1, 3), certainty: "Very low", existingStudies: 1, policyArea: "Mental-health services", publicationStatus: "conference_abstract",
  },
  {
    id: "SYN-032", title: "Shade structures in school playgrounds and pupil heat exposure in Bulawayo: a pilot study",
    summary: "Shade sails were installed at four schools and compared with four matched schools. Shaded schools had lower playground temperatures and fewer reported heat symptoms.",
    year: 2026, language: "English", country: "Zimbabwe", region: "Southern Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Non-randomised", population: "Primary school pupils", exposure: "School playground heat", outcomeText: "Cooling intervention and heat symptoms", mappedOutcome: "O7", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 2, 1, 2, 1, 3), certainty: "Very low", existingStudies: 2, newInterventionClass: true, progressPlus: ["Age", "School setting"], policyArea: "School heat protection", publicationStatus: "published",
  },
  {
    id: "SYN-033", title: "Heat exposure and pregnancy outcomes among subsistence farmers in rural Burkina Faso",
    summary: "A cohort of 890 pregnancies in rural farming communities linked workload and ambient temperature to birth outcomes. All participants lived in rural districts.",
    year: 2026, language: "English", country: "Burkina Faso", region: "West Africa", setting: "Rural", recordType: "Journal article", studyDesign: "Cohort", population: "Pregnant subsistence farmers", exposure: "Agricultural heat and workload", outcomeText: "Birthweight", mappedOutcome: "O5", relevanceLabel: "Mostly", scopeIssue: "Rural Burkina Faso falls outside the current African urban population scope.", scopeStatus: "out_of_scope", signalEligible: false, scores: score(2, 2, 2, 1, 2, 1, 3), certainty: "Very low", existingStudies: 3, progressPlus: ["Place of residence", "Occupation", "Pregnancy"], publicationStatus: "published",
  },
  {
    id: "SYN-034", title: "Daily temperature and all-cause mortality in Lagos: an 11-year analysis",
    summary: "Mortality records from Lagos State, 2014–2025, were analysed using case-crossover methods. Elevated mortality occurred above the 92nd temperature percentile; this is the largest West African analysis to date.",
    year: 2026, language: "English", country: "Nigeria", region: "West Africa", setting: "Urban", recordType: "Journal article", studyDesign: "Case-crossover", population: "Lagos State population", exposure: "Ambient temperature", outcomeText: "All-cause mortality", mappedOutcome: "O1", relevanceLabel: "Direct", scopeStatus: "signal", signalEligible: true, scores: score(3, 2, 2, 1, 2, 1, 1), certainty: "Moderate", existingStudies: 14, contextGap: "West African mortality evidence", progressPlus: ["Place of residence", "Geographic context"], policyArea: "Heat-health planning", publicationStatus: "published",
  },
];

export const allComputedRecords = recordSeeds;
