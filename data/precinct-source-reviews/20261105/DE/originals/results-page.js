
if ('scrollRestoration' in history) {
        history.scrollRestoration = 'manual';
}
const fileName = window.location.pathname.split('/').pop();
const electionId = fileName.substring(0, fileName.lastIndexOf('.')).toUpperCase();
async function getResults(resultType = "Statewide",selection="") {
    let Results
    let jsonFields
    let tbl
    //let spinner = document.getElementById('loading-overlay');
    //spinner.style.opacity=1
    //spinner.style.display="inline-block"
    let tstamp = new Date().getTime()
    let turnoutPath=`/results/enr/Election_VoterTurnout_ID_${electionId}.json?t=${tstamp}`
    let state_json =`/results/enr/Election_StatewideResults_ID_${electionId}.json?t=${tstamp}`
    try {
        // 1. Show the spinner right as the operation begins
        new Date().getTime()
        let jsonPath=""  
        switch (resultType){
            case "Statewide":
                jsonPath = `/results/enr/Election_StatewideResults_ID_${electionId}.json?t=${tstamp}`
                jsonFields = ["Candidate Name","Party Name","Machine Votes","Absentee Votes","Early Voting Votes","Total Votes","Percentage"]
                tbl = document.getElementById("st")
                if (tbl.getAttribute("data-exists")) {return}
                break;
            case "Representative District":
                jsonPath = `/results/enr/Election_ByRepresentativeDistrict_ID_${electionId}.json?t=${tstamp}`
                jsonFields = ["Candidate Name","Party Name","Machine Votes","Absentee Votes","Early Voting Votes","Total Votes","Percentage"]
                tbl = document.getElementById("dist")
                if (tbl.getAttribute("data-exists")) {return}
                break;
            case "Election District":
                jsonPath = `/results/enr/Election_ByElectionDistrict_ID_${electionId}.json?t=${tstamp}`
                jsonFields = ["Candidate Name","Party Name","Machine Votes","Absentee Votes","Early Voting Votes","Total Votes","Percentage"]
                tbl = document.getElementById("ed")
                if (tbl.getAttribute("data-exists")) {return}
                break;
            case "County":
                jsonPath = `/results/enr/Election_ByCountyWithWilmington_ID_${electionId}.json?t=${tstamp}`
                jsonFields = ["Candidate Name","Party Name","New Castle","Kent","Sussex","State","Percentage"]
                tbl = document.getElementById("cty")
                if (tbl.getAttribute("data-exists")) {return}
                break
            case "CountyAndWilmington":
                jsonPath = `/results/enr/Election_ByCountyWithWilmington_ID_${electionId}.json?t=${tstamp}`
                jsonFields = ["Candidate Name","Party Name","Wilmington","Rest of New Castle","Kent","Sussex","State","Percentage"]
                tbl = document.getElementById("wilm")
                if (tbl.getAttribute("data-exists")) {return}
                break;
        }
        
        const response = await fetch(jsonPath);
        Results = await response.json();

        //Some json files dont seem to have a time and we don't want multiple different stamps anyway.  So we'll use the statewide for the page
        let updatedEnr = document.getElementById("enr-updated")

        if (resultType !="Statewide") {
            // fetch the statewide json
            const state_response = await fetch(state_json);
            let state_result = await state_response.json();
            let rptdt = new Date(state_result[0]["ReportTime"])
            let dtfDate = new Intl.DateTimeFormat('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' });
            let dtfTime = new Intl.DateTimeFormat('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
            let formattedDate = `${dtfDate.format(rptdt)} ${dtfTime.format(rptdt)}`
            updatedEnr.textContent = `Data as of ${formattedDate} `
            updateSummary(state_result)
            getTurnout(turnoutPath)
        }
        if (resultType == "Statewide") {
            let rptdt = new Date(Results[0]["ReportTime"])
            let dtfDate = new Intl.DateTimeFormat('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' });
            let dtfTime = new Intl.DateTimeFormat('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
            let formattedDate = `${dtfDate.format(rptdt)} ${dtfTime.format(rptdt)}`
            updatedEnr.textContent = `Data as of ${formattedDate} `
            
            
            updateSummary(Results)
            getTurnout(turnoutPath)
            }


        //Replaced with static list so that we don't have to wait for list to regenerate during page refresh
        // Create unique array of contest titles for race selection
        // var nameofraces = [...new Set(Results.map(r => r["Contest Title"]))];
        // var selectRace = document.getElementById("enr-races")
        //selectRace.innerHTML = `<option value="">Select a Race</option>`
        //nameofraces.forEach(function (race) {
        //selectRace.innerHTML += `<option value="${race.replace(/[\W_]/g, "")}">${race}</option>`;
        //console.log( `<option value="${race.replace(/[\W_]/g, "")}">${race}</option>`)
        //});
        


        let tblHTML = ""
        let data
        if (resultType == "Statewide" || resultType == "County" || resultType == "CountyAndWilmington") {
            data = Results.reduce(function (r, a) {
                    r[a["Contest Title"]] = r[a["Contest Title"]] || [];
                    r[a["Contest Title"]].push(a);
                    return r;
                }, Object.create(null));
            // Iterate through each Contest and generate the HTML
            Object.entries(data).forEach(contest => {
                //console.log(contest)
                //tblHTML += "<h3>" + contest[0] + "</h3>"
                
                
                //Taable is per contest not per party/candidate
                let classname = contest[0]
                    tblHTML += `<table class='lighthouse-table mb-2 ${classname.replace(/[\W_]/g, "")}'>`
                    tblHTML += `<caption>${contest[0]}</caption>`
                    tblHTML += "<thead>"
                    tblHTML += "<tr>"
                    jsonFields.forEach(FieldName => {
                            tblHTML += `<th>${FieldName}</th>`
                        })
                    tblHTML += "</tr>"
                    tblHTML += "</thead>"
                    tblHTML += "<tbody>"
                    Object.entries(contest[1]).forEach(candidate => {
                        tblHTML += "<tr>"
                        jsonFields.forEach(FieldName => {
                            tblHTML += `<td data-label="${FieldName}">${candidate[1][FieldName]}</td>`
                        })
                        tblHTML += "</tr>"
                    }) 
                    tblHTML += "</tbody>"
                    tblHTML += "</table>"
            })
        }

        if (resultType == "Representative District" || resultType == "Election District"){
            //contest, then district,then party
            let contest = Results.reduce(function (r, a) {
                    r[a["Contest Title"]] = r[a["Contest Title"]] || [];
                    r[a["Contest Title"]].push(a);
                    return r;
                }, Object.create(null));
            Object.entries(contest).forEach(contest => {
                let district = contest[1].reduce(function (r, a) {
                    r[a[resultType]] = r[a[resultType]] || [];
                    r[a[resultType]].push(a);
                    return r;
                }, Object.create(null));
                
                Object.entries(district).forEach(district =>{
/*                    let party = district[1].reduce(function (r, a) {
                    r[a["Party Name"]] = r[a["Party Name"]] || [];
                    r[a["Party Name"]].push(a);
                    return r;
                    }, Object.create(null));
*/
                    let classname = district[1][0]["Contest Title"]
                    tblHTML += `<table class='lighthouse-table mb-2 ${classname.replace(/[\W_]/g, "")}'>`
                    tblHTML += `<caption>${contest[0]}<br>${district[0]}</caption>`
                    tblHTML += "<thead>"
                    tblHTML += "<tr>"
                    jsonFields.forEach(FieldName => {
                            tblHTML += `<th>${FieldName}</th>`
                        })
                    tblHTML += "</tr>"
                    tblHTML += "</thead>"
                    tblHTML += "<tbody>"
                    /*
                    Object.entries(district).forEach(candidate =>{
                    let classname = primary[1][0]["Contest Title"]
 */       
                    
                        Object.entries(district[1]).forEach(candidate => {

                            tblHTML += "<tr>"
                            jsonFields.forEach(FieldName => {
                                tblHTML += `<td data-label="${FieldName}">${candidate[1][FieldName]}</td>`
                            })

                            tblHTML += "</tr>"

                        })
/*
                    })
                      */                  
                    tblHTML += "</tbody>"
                    tblHTML += "</table>"
                })
            })

 
        }
        tbl.innerHTML = tblHTML
        tbl.setAttribute('data-exists', 'true');

        // Refresh based on url params
        const url = new URL(window.location.href)
        var selectRace = document.getElementById("enr-races")
        let selection = url.searchParams.get("filter")
        filterReport(selectRace,selection)

        let targetScroll = url.searchParams.get("tmp_scroll")
        await waitUntilLayoutReady(targetScroll)
        window.scrollTo(0, targetScroll);
        //after scroll remove the tmp_scroll from the URL or the user will have a strange experience when manually refreshing
        url.searchParams.delete("tmp_scroll")
        history.replaceState(null,"",url.search)
       
    }
    catch (error){
    console.log(error);
    }
    finally {

    }
    
}
async function getTurnout(jsonFile){
    try {
    const response = await fetch(jsonFile);
    Results = await response.json();
    let votedata = Results.reduce(function (r, a) {
                    r[a["Representative District"]] = r[a["Representative District"]] || [];
                    r[a["Representative District"]].push(a);
                    return r;
                }, Object.create(null));
                const castcnt = votedata["ALL"][0]["Ballots Cast"]
                const votercnt = "810,407" //votedata["ALL"][0]["Reg Voters"] //May need to be hardcoded
                const turnoutpct = votedata["ALL"][0]["Percentage"] 
                let cnt = document.getElementById("vote-count")
                let pct = document.getElementById("vote-percent")
                let voteprog = document.getElementById("vote-progress")
                cnt.innerHTML=`${castcnt} of ${votercnt}`
                pct.innerHTML=`${turnoutpct}%`
                voteprog.value = turnoutpct
    }
    catch(error){}
    finally{}
}
function setActiveButton(btn) {
    let stbtn = document.getElementById("contest-group-statewide")
    let distbtn = document.getElementById("contest-group-district")
    let edbtn = document.getElementById("contest-group-ed")
    let ctybtn = document.getElementById("contest-group-county")
    let wilmbtn = document.getElementById("contest-group-wilm")
    let st = document.getElementById("st")
    let dist = document.getElementById("dist")
    let ed = document.getElementById("ed")
    let cty = document.getElementById("cty")
    let wilm = document.getElementById("wilm")
    let grp = document.getElementById("enr-active-group")

    stbtn.classList.remove("btn-yellow")
    distbtn.classList.remove("btn-yellow")
    edbtn.classList.remove("btn-yellow")
    ctybtn.classList.remove("btn-yellow")
    wilmbtn.classList.remove("btn-yellow")
    stbtn.classList.add("btn-primary")
    distbtn.classList.add("btn-primary")
    edbtn.classList.add("btn-primary")
    ctybtn.classList.add("btn-primary")
    wilmbtn.classList.add("btn-primary")
    if (!btn) {
        btn = stbtn
    }
    const url = new URL(window.location.href)
    let grpParam
    let grpFilter = url.searchParams.get("filter")
    let tmpScroll = url.searchParams.get("tmp_scroll")
    switch (btn.id){
        case "contest-group-statewide":
            btn.classList.remove("btn-primary")
            btn.classList.add("btn-yellow")
            //Show selected section and hide others
            st.classList.remove("noshow")
            dist.classList.add("noshow")
            ed.classList.add("noshow")
            cty.classList.add("noshow")
            wilm.classList.add("noshow")  
            grp.textContent="Statewide" 
            getResults("Statewide",grpFilter)
            grpParam = "Statewide"
            break;
        case "contest-group-district":
            btn.classList.remove("btn-primary")
            btn.classList.add("btn-yellow")
            st.classList.add("noshow")
            dist.classList.remove("noshow")
            ed.classList.add("noshow")
            cty.classList.add("noshow")
            wilm.classList.add("noshow")    
            grp.textContent="Representative District"
            getResults("Representative District",grpFilter)
            grpParam = "Representative%20District"
            break;
        case "contest-group-ed":
            btn.classList.remove("btn-primary")
            btn.classList.add("btn-yellow")
            st.classList.add("noshow")
            dist.classList.add("noshow")
            ed.classList.remove("noshow")
            cty.classList.add("noshow")
            wilm.classList.add("noshow") 
            grp.textContent="Election District" 
            getResults("Election District",grpFilter)
            grpParam = "Election%20District"
            break;
        case "contest-group-county":
            btn.classList.remove("btn-primary")
            btn.classList.add("btn-yellow")
            st.classList.add("noshow")
            dist.classList.add("noshow")
            ed.classList.add("noshow")
            cty.classList.remove("noshow")
            wilm.classList.add("noshow") 
            grp.textContent="County"
            getResults("County",grpFilter)
            grpParam = "County"
            break;
        case "contest-group-wilm":
            btn.classList.remove("btn-primary")
            btn.classList.add("btn-yellow")
            st.classList.add("noshow")
            dist.classList.add("noshow")
            ed.classList.add("noshow")
            cty.classList.add("noshow")
            wilm.classList.remove("noshow") 
            grp.textContent="County with Wilmington" 
            getResults("CountyAndWilmington",grpFilter)
            grpParam = "CountyAndWilmington"
            break;
    }
    if (tmpScroll == null) {
        history.replaceState(null,"",`?group=${grpParam}&filter=${grpFilter}`)
    }
    else {
        history.replaceState(null,"",`?group=${grpParam}&filter=${grpFilter}&tmp_scroll=${tmpScroll}`)
    }
}
function updateSummary(results) {
    var maxPrecinctsReported = Math.max(...results.map(result => result["Precincts Reported"]));
    var maxTotalPrecincts = Math.max(...results.map(result => result["Total Precincts"]));
    // Add title and update date information
    //var electionYear = moment(results[0]["Election Date"]).format('YYYY');
    var electionName = results[0]["Election Name"];
    var typeresults = results[0]["Results Type"];
    var typeresultsHtml;
    let precintcnt = document.getElementById("precinct-count")
    let precintpct = document.getElementById("precinct-percent")
    let precintprog = document.getElementById("precinct-progress")

    precintcnt.innerHTML=`${maxPrecinctsReported} of ${maxTotalPrecincts} election districts reporting`
    let precinctcalc = maxPrecinctsReported / maxTotalPrecincts * 100.00
    //precinctcalc > 99 ? 99 : precinctcalc; //comment after close
    precintpct.innerHTML =`${precinctcalc.toFixed(0)}%`
    precintprog.value=precinctcalc

    if (typeresults === "OFFICIAL RESULTS") {
        typeresultsHtml = `<h3 id="enr-result-type"><i class="fa-regular fa-circle-check" style="color:green" aria-hidden="true"></i> ${typeresults}</h3>` ;
    } else {
        typeresultsHtml = `<h3 id="enr-result-type">${typeresults}</h3>`;
    }
    resultHeader=document.getElementById("enr-result-type")
    resultHeader.outerHTML = typeresultsHtml
}
function filterReport(contest, selection="") {
    const optvals = Array.from(contest.options).map(option => option.value);
    const url = new URL(window.location.href)
    if (selection != ""){
        contest.value=selection
    }
    if (contest.value=="") {
        optvals.forEach( function(opt){
            if (opt !== ""){ //show all values when nothing is selected
                let els = Array.from(document.getElementsByClassName(opt))
                els.forEach(el => {el.classList.remove("noshow")})
            }
        })
    }
    if (contest.value !== "") {
        optvals.forEach( function(opt){
            if (opt == ""){ return } //exit for blank item in list 
            if (opt == contest.value) { //Show selected contest
                let els = Array.from(document.getElementsByClassName(contest.value))
                els.forEach(el => {el.classList.remove("noshow")})              
            } else { //hide contests that are not selected
                let els = Array.from(document.getElementsByClassName(opt))
                els.forEach(el => {el.classList.add("noshow")})                 
            }
        })
    }
    url.searchParams.set("filter", contest.value)
    history.replaceState(null,"",url.search)
}
function waitUntilLayoutReady(targetScroll) {
  return new Promise((resolve) => {
    function checkHeight() {
      // Is the page height physically long enough to reach our destination?
      if (document.documentElement.scrollHeight >= targetScroll) {
        resolve();
      } else {
        // If not, wait for the next frame recalculation and try again
        requestAnimationFrame(checkHeight);
      }
    }
    checkHeight();
  });
}

function reloadPage(){
    const url = new URL(window.location.href);
    let pos = Math.round(window.scrollY)
    url.searchParams.set("tmp_scroll", pos);
    history.replaceState(null,"",url.search)
    window.location.reload()
}


function initPage (){
    //should be 300000 when not testing
    const reloader = setTimeout(reloadPage,300000)

    if (window.location.search == "") {
        getResults("Statewide")
        history.replaceState(null,"","?group=state&filter=")
    } 
    else {
        //Restore prior state from URL params
        const url = new URL(window.location.href);
        let grp = url.searchParams.get("group")
        let flt = url.searchParams.get("filter")
        let btn
        //Restore button group
        switch (grp){
            case "Statewide":
                btn = document.getElementById("contest-group-statewide")
                break;
            case "Representative District":
                btn = document.getElementById("contest-group-district")
                break;
            case "Election District":
                btn = document.getElementById("contest-group-ed")
                break;
            case "County":
                btn = document.getElementById("contest-group-county")
                break
            case "CountyAndWilmington":
                btn = document.getElementById("contest-group-wilm")
                break
        }
        setActiveButton(btn)
    }
}
initPage()
