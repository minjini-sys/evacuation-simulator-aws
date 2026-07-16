/**
 * Created by Il Yeup, Ahn in KETI on 2017-02-23.
 */

/**
 * Copyright (c) 2018, OCEAN
 * All rights reserved.
 * Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
 * 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
 * 3. The name of the author may not be used to endorse or promote products derived from this software without specific prior written permission.
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

/* =================================================================
   [IoT Server 설정 파일: conf.js]
   여기서 여러분의 프로젝트에 맞는 AE(프로젝트명)와 CNT(데이터 종류)를 정의합니다.

   실습은 제공받은 소스코드를 그대로 사용하되, 추후 각자 응용을 진행할 때 수정하면 됩니다.
   
   ★중요★: 여기서 정한 이름들은 나중에 Python 에이전트의 .env 파일과 
            반드시 "똑같이" 맞춰야 합니다.
   ================================================================= */

var ip = require("ip");

var conf = {};
var cse = {};
var ae = {};
var cnt_arr = [];
var sub_arr = [];
var acp = {};

conf.useprotocol = 'http'; 

conf.sim = 'disable'; 

// build cse (Mobius 플랫폼 기본 설정 - 보통 그대로 둠)
cse.host        = process.env.MOBIUS_HOST || '158.179.161.105';
cse.port        = process.env.MOBIUS_HTTP_PORT || '7579';
cse.name        = 'Mobius';
cse.id          = '/Mobius2';
cse.mqttport    = process.env.MOBIUS_MQTT_PORT || '1883';
cse.wsport      = process.env.MOBIUS_WS_PORT || '7577';

// ------------------------------------------------------------------
// ▼▼▼ [학생 설계 구간 1] AE (Application Entity) 설정 ▼▼▼
// AE는 여러분의 '프로젝트 이름'과 같습니다.
// ------------------------------------------------------------------
ae.name         = process.env.MOBIUS_AE || 'FacialEmo'; 
// [수정 가이드]
// 위 'FacialEmo'를 여러분의 프로젝트 주제로 바꾸세요.
// 예: 행동인식 프로젝트라면 -> 'Action_Project'
// 예: 스마트팜 프로젝트라면 -> 'Smart_Farm'
// ★주의★: 여기서 바꾼 이름을 .env 파일의 "MOBIUS_AE" 값에 똑같이 적어야 합니다.

ae.id           = 'S'+ae.name;
ae.parent       = '/' + cse.name;
ae.appid        = 'sonic_emotion';
ae.port         = process.env.AE_HTTP_PORT || '9727';
ae.bodytype     = 'json'; 
ae.tasport      = process.env.TAS_PORT || '3105';

// ------------------------------------------------------------------
// ▼▼▼ [학생 설계 구간 2] CNT (Container) 설정 ▼▼▼
// CNT는 AE 안에 있는 '데이터 담는 그릇'입니다. (센서 종류 등)
// ------------------------------------------------------------------
var count = 0;
cnt_arr[count] = {};
cnt_arr[count].parent = '/' + cse.name + '/' + ae.name;
cnt_arr[count++].name = 'gesture';

// cnt_arr[count] = {};
// cnt_arr[count].parent = '/' + cse.name + '/' + ae.name;

// cnt_arr[count++].name = 'emotion';
// [수정 가이드]
// 위 'emotion'을 여러분이 다루는 데이터 종류로 바꾸세요.
// 예: 행동 데이터를 담는다면 -> 'Action'
// 예: 온도 데이터를 담는다면 -> 'temperature'
// ★주의★: 여기서 바꾼 이름을 .env 파일의 "MOBIUS_CONTAINER" 값에 똑같이 적어야 합니다.


// [심화: 컨테이너가 여러 개 필요할 때 주석을 풀고 사용하세요]
// cnt_arr[count] = {};
// cnt_arr[count].parent = '/' + cse.name + '/' + ae.name;
// cnt_arr[count++].name = 'co2';  // 예: 이산화탄소 센서
// cnt_arr[count] = {};
// cnt_arr[count].parent = '/' + cse.name + '/' + ae.name;
// cnt_arr[count++].name = 'temp'; // 예: 온도 센서

// --------------------------------------- 이하 수정 불필요 ---------------------------------------------

// build sub
count = 0;
sub_arr[count] = {};
sub_arr[count].parent = '/' + cse.name + '/' + ae.name + '/' + cnt_arr[0].name;
sub_arr[count].name = 'sub';
// MQTT notification으로 받기 (Mcp_Server.py가 MQTT 구독)
sub_arr[count++].nu = 'mqtt://' + cse.host + '/' + ae.id + '?ct=' + ae.bodytype;

// Mcp_Server.py를 위한 추가 subscription (브로드캐스트 토픽)
sub_arr[count] = {};
sub_arr[count].parent = '/' + cse.name + '/' + ae.name + '/' + cnt_arr[0].name;
sub_arr[count].name = 'sub-mcp';
sub_arr[count++].nu = 'mqtt://' + cse.host + '/Mobius/' + ae.name + '?ct=' + ae.bodytype;

// --------
// sub_arr[count] = {};
// sub_arr[count].parent = '/' + cse.name + '/' + ae.name + '/' + cnt_arr[1].name;
// sub_arr[count].name = 'sub';
// sub_arr[count++].nu = 'mqtt://' + cse.host + '/' + ae.id + '?ct=' + ae.bodytype; // mqtt
//sub_arr[count++].nu = 'http://' + ip.address() + ':' + ae.port + '/noti?ct=json'; // http
//sub_arr[count++].nu = 'Mobius/'+ae.name; // mqtt
// --------

// sub_arr[count] = {};
// sub_arr[count].parent = '/' + cse.name + '/' + ae.name + '/' + cnt_arr[1].name;
// sub_arr[count].name = 'sub1';
// sub_arr[count++].nu = 'mqtt://' + cse.host + '/' + ae.id + '1?ct=json'; // mqtt
// sub_arr[count] = {};
// sub_arr[count].parent = '/' + cse.name + '/' + ae.name + '/' + cnt_arr[1].name;
// sub_arr[count].name = 'sub2';
// sub_arr[count++].nu = 'mqtt://' + cse.host + '/' + ae.id + '2?ct=json'; // mqtt
// sub_arr[count] = {};
// sub_arr[count].parent = '/' + cse.name + '/' + ae.name + '/' + cnt_arr[1].name;
// sub_arr[count].name = 'sub3';
// sub_arr[count++].nu = 'mqtt://' + cse.host + '/' + ae.id + '3?ct=json'; // mqtt


/*// --------
sub_arr[count] = {};
sub_arr[count].parent = '/' + cse.name + '/' + ae.name + '/' + cnt_arr[1].name;
sub_arr[count].name = 'sub2';
//sub_arr[count++].nu = 'http://' + ip.address() + ':' + ae.port + '/noti?ct=json'; // http
//sub_arr[count++].nu = 'mqtt://' + cse.host + '/' + ae.id + '?rcn=9&ct=' + ae.bodytype; // mqtt
sub_arr[count++].nu = 'mqtt://' + cse.host + '/' + ae.id + '?ct=json'; // mqtt
// -------- */

// build acp: not complete
acp.parent = '/' + cse.name + '/' + ae.name;
acp.name = 'acp-' + ae.name;
acp.id = ae.id;


conf.usesecure  = 'disable';

if(conf.usesecure === 'enable') {
    cse.mqttport = '8883';
}

conf.cse = cse;
conf.ae = ae;
conf.cnt = cnt_arr;
conf.sub = sub_arr;
conf.acp = acp;


module.exports = conf;
