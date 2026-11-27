export function effectReading(view, units = "democratic_two_party_share", group = "", office = "house") {
  if (view.startsWith("scenario_")) {
    const outcome = view === "scenario_retaining" ? "assigned the same party"
      : view === "scenario_switching" ? "assigned a switch between Democratic and Republican choice"
        : "assigned no current-contest choice";
    return { title: "A modeled share, not a change in vote share",
      meaning: `Of the source weight recalling a 2024 Democratic or Republican presidential choice${group ? " in the selected group" : ""}, this percentage is ${outcome}. It is not a percentage of all voters or verified individual histories.`,
      example: "For example, 10% means 10 out of every 100 recalled major-party source choices in this scenario. No current-contest choice does not confirm staying home." };
  }
  if (["source_retaining", "retaining"].includes(view)) return {
    title: "Percentage keeping the same party in the model",
    meaning: `The denominator is previous Democratic or Republican House source choices${group ? " within the selected group" : ""}. The numerator is modeled D→D plus R→R choices. This is not a share of all residents or all current voters.`,
    example: "For example, 80% means 80 of every 100 prior D/R source choices are assigned the same party—not that the other 20% all switched; they can also enter other or no-choice categories.",
  };
  const share = office === "house" && units === "democratic_two_party_share";
  const unitsText = share ? "Democratic share = D ÷ (D + R); other-party choices are excluded."
    : "D−R margin = (D − R) ÷ (D + R); other-party choices are excluded.";
  const metric = view.replace(/^source_/, "");
  const mechanism = ["participation", "modeled_nonparticipation"].includes(metric)
    ? "The net contribution combines entry into and exit from a Democratic or Republican contest choice. It is not a turnout rate or a count of people staying home."
    : metric === "switching" ? "This is the modeled contribution of D↔R choice changes—not the percentage of people who switched parties."
      : metric === "entry" ? "This is the modeled contribution of no prior contest choice → D/R. It does not identify first-ever or returning voters."
        : metric === "exit" ? "This is the modeled contribution of prior D/R → no current contest choice. No contest choice does not prove someone stayed home; they might skip this race."
          : ["other", "other_choice"].includes(metric) ? "This is the modeled contribution of changes involving other or unassigned party choices—not nonvoting."
            : metric === "unresolved" ? "This is the modeled contribution involving unresolved responses. Unknown responses are not counted as staying home."
              : "This is the total change, not the percentage who switched parties or stayed home.";
  return {
    title: `Percentage-point ${["total", "reported_total", "reported_counts"].includes(metric) ? "change" : "contribution"} in ${share ? "Democratic vote share" : "the D−R margin"}`,
    meaning: `${mechanism}${group ? " The selected group's contribution uses the statewide denominator, not a within-group turnout rate." : ""} ${unitsText}`,
    example: share ? "Example: 45% → 50% Democratic share is +5 percentage points (pp), toward Democrats. A negative number is toward Republicans."
      : "Example: R+4 → D+6 is +10 margin points (pp), toward Democrats. A negative number is toward Republicans.",
  };
}
