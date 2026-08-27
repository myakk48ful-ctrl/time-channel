<?php
/* <===> All rights reserved by @itsNull <===> */
error_reporting(0);
define('API_KEY', 'TOKEN'); # [!] EDIT [!]
date_default_timezone_set('Asia/Tehran');

$chat = '-1212'; # [!] EDIT [!]
$channel_name = 'IRA_Team'; # [!] EDIT [!]
$res = sendMessage($chat, ".");
setChatTitle($chat, "$channel_name | ".date('H:i'));
deleteMessage($chat, $res->result->message_id);
deleteMessage($chat, $res->result->message_id + 1);

function bot($method, $datas = []) {
    $url = "https://api.telegram.org/bot".API_KEY."/".$method;
    $ch = curl_init();
    curl_setopt($ch,CURLOPT_URL,$url);
    curl_setopt($ch,CURLOPT_RETURNTRANSFER,true);
    curl_setopt($ch,CURLOPT_POSTFIELDS,$datas);
    $res = curl_exec($ch);
    if(curl_error($ch)) {
        var_dump(curl_error($ch));
    }
    return json_decode($res, true);
}
function sendMessage($user, $msg, $reply = -1, $key = null, $preview = false) {
	return bot('sendMessage', [
        'chat_id' => $user,
        'text' => $msg,
        'parse_mode' => "HTML",
        'reply_to_message_id' => $reply,
        'reply_markup' => $key,
		'disable_web_page_preview' => $preview
    ]);
}
function deleteMessage($chat_id, $message_id) {
	return bot('deleteMessage', [
        'chat_id' => $chat_id,
        'message_id' => $message_id
    ]);
}
function setChatTitle($chat_id, $title) {
	return bot('setChatTitle', [
        'chat_id' => $chat_id,
        'title' => $title
    ]);
}