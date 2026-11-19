"""Scoped Chinese labels with SHA-256 matches for locally sourced text."""

# Manifest matches include the exact source case, punctuation and spacing.
PANELS = {
    'timing_panel': {
        'positionLabel': {
            'ae98ea9a0b492289b25d3d0ee783a63de32f3a842bf556e2281863556d83171c': '名次',
        },
        'lapLabel': {
            'c4356b7f4136bad32649aea79f819d4b048b897e70c44b985f21b33ae6042e88': '圈数',
        },
        'currentLabel': {
            'e3cc57e193d6512e6debf0e925febe757e87e85d66150a2f212aa8641940b027': '当前圈',
        },
        'lastLabel': {
            '7e86aeec84c6da788048785610219e2adbafa0b6f17d572697951ab45e93e81e': '上圈',
        },
        'bestLabel': {
            '16b7940e30c20d40fbf33678ab8eba9d289148d7932dd3fa8c6d92cdf9947b17': '最快',
        },
        'editMode__label': {
            '2b43838b89d0f756ad6f04cabbb9550f53adb70cc528a9db0309679ef63dc5f4': '计时面板',
        },
    },
    'pit_limiter': {
        'header': {
            '63e6f2d134f98709baf9fa8c05edf0a9e215dca26cd5b1dfae582f28110d0c41': '维修区内',
        },
        'speedLimitLabel': {
            '2668af97b3dc8712cdee95257f96dd2280d1b2e0ae6f517b4e3a9a96f275e5f4': '维修区限速：',
        },
        'currentSpeedLabel': {
            'a0d17028930f6daee97c272722d33c1a585fec3ccaf290d4c72bd0b8017a4093': '当前车速：',
        },
        'editMode__label': {
            '27b507c928374c2beb3333f00ef2baccd277bc9db0ae8b3bae9147b2769e3d1c': '进站限速',
        },
    },
    'status_strip': {
        'pitWindowOpensIn': {
            '899e6540d6e408a4d38abf73df4574149ea7eda61214e962a0051842a9c94c90': '进站窗口开放还剩 ',
            'e905bddd92a277d155f814d56045d33a467f6607acc8861b013c6946e642bddf': ' 圈',
            'b470abb701b6657a3c037523627c1dacc3e79c0c95a70cb00540ccb9e56911a4': ' 圈',
            '144ded65d8e7ec777abc15f15f3ec10b2acee4c3f8f4a24ea7bce26ffbeafa06': ' 分钟',
        },
        'pitWindowOpen': {
            'b5cf5e67f4c759556fec3239db2706d03d2a410ee968b26bb8de10e6d315ef9e': '进站窗口已开放',
        },
        'pitWindowClosed': {
            '3432a435a9357fb6c2a2656cec086a44ccc783b9abd0bf4b02c3d4c622f54008': '进站窗口已关闭',
        },
        'pitWindowClosing': {
            '76a3d719b778237178dc94f6777c8bedd4e21ce247fb6ece7d6c2f9b7a7d4dc1': '进站窗口关闭还剩 ',
            'e905bddd92a277d155f814d56045d33a467f6607acc8861b013c6946e642bddf': ' 圈',
            'b470abb701b6657a3c037523627c1dacc3e79c0c95a70cb00540ccb9e56911a4': ' 圈',
            '144ded65d8e7ec777abc15f15f3ec10b2acee4c3f8f4a24ea7bce26ffbeafa06': ' 分钟',
        },
        'driveThroughLabel': {
            'a75eabf0bbea12c097e4c2df3b1315403d35468b1ad0a0955c0f8f42b35dedb7': '通过维修区处罚',
        },
        'driveThroughReason': {
            '01d34df6fe64f1fa2432d193c0b56fa753c4324c24511b5e8c24b4d199f147a9': '切赛道',
            '1787bde5a3935160161ffd7fd0c4c75cb8947a442aa5ed89dc710fce07779393': '维修区超速',
            '909ac5204492e031aa528dc062cb43737b99a24b00f177aee63e968d1b526733': '抢跑',
            '612a03f60f795e2bce23c0ee61bc2df4a06abb58e2b2c607cb18fb00908ea33c': '无视蓝旗',
            'cfe9f4b1b2c5ba046053e75fbcbafde653c7733bb84bdab752e748cc861db162': '车速过低',
            'd3c91e62288622a9852492d8cca5452e7ff43c173ddb733c09613bdf674c5541': '绿旗前超车',
            '5c896b33b144cdbd98048a356c01297d578b827dd393bacf38edc46b00d20188': '违规超车',
            'c27d602fddbf5e03e2497158643a10ff010325fd4d4a46ac60eebaa0f1dfa241': '在维修区入口违规超车',
            'eb13e1a4873be04cb777b6ab026ddc1be11784b20d39f79241202d3355254fa3': '未执行减速处罚',
        },
        'driveThroughServeWithin': {
            '9f1f5803d8fb7087e26a20c1c69aaec815f6b26ad3315320bf04348a69289c44': '请在 ',
            'b470abb701b6657a3c037523627c1dacc3e79c0c95a70cb00540ccb9e56911a4': ' 圈内执行处罚',
        },
        'driveThroughServeNow': {
            '43c2035964e7c82b5b120d9871b362dd20c9dd9bf0b15a90ee9f0aab44510fe9': '本圈须执行处罚，否则取消资格',
        },
        'pitStopLabel': {
            'b279f46b6291907b7b52110d2e7e136d03f119db8b9935bebe0796da7b1aab3a': '进站停车处罚',
        },
        'pitStopServeWithin': {
            '9f1f5803d8fb7087e26a20c1c69aaec815f6b26ad3315320bf04348a69289c44': '请在 ',
            'b470abb701b6657a3c037523627c1dacc3e79c0c95a70cb00540ccb9e56911a4': ' 圈内执行处罚',
        },
        'pitStopServeNow': {
            '43c2035964e7c82b5b120d9871b362dd20c9dd9bf0b15a90ee9f0aab44510fe9': '本圈须执行处罚，否则取消资格',
        },
        'lapInvalidLabel': {
            'f73a4f80776cac9af2808f8afd35009be737e06df3b8dc4fbfba420f5b2142b6': '本圈和下一圈成绩无效',
            '0fdfdc1393f50401843b0c9bfed350fc386a96ef99f34e03b7bf7e50a5026655': '本圈成绩无效',
        },
        'lapInvalidReason': {
            '700a80df2eae99f0ffc0cd4791fa8f965a57e39cd9a53b28bb7c3a7921916505': '四轮越过白线',
            '9cd4a271d368e3237e11ece3b896d7e2597339dd6bbbeb02983dde305f0319e9': '过度碰撞',
            '1787bde5a3935160161ffd7fd0c4c75cb8947a442aa5ed89dc710fce07779393': '维修区超速',
            '0483d9b76de304242e14caef9f0c5a6ff4271ba18dd94c80984a1d79b17bd22b': '撞墙',
            'cfa75d85632f6124beeaf6f3d266ffd38d058d5b8b971710316e6ccd8d16b58b': '逆向行驶',
        },
        'wrongWayLabel': {
            'cfa75d85632f6124beeaf6f3d266ffd38d058d5b8b971710316e6ccd8d16b58b': '逆向行驶',
        },
        'dqLabel': {
            '35eb44396cd1aae21029ea63a8816b05256fa3ffa76e64e95bad8ecca17cb108': '已取消资格',
        },
        'dnfLabel': {
            '58a259f5e8f8cc8970217e6f0aaf9233b8aead0888324fe04e338367ce56ba17': '未完赛',
        },
        'dnsLabel': {
            'a3cc676b9e48e43e022f20db6ff98a31fc724bf0731d8f9a177ebd073d9fad44': '未发车',
        },
        'stopAndGoLabel': {
            '9474b841590098fcd1ebba251e1e1e3953c48ded959fec3661bbde473ccb0e07': '进站停走处罚',
        },
        'stopAndGoServeWithin': {
            '9f1f5803d8fb7087e26a20c1c69aaec815f6b26ad3315320bf04348a69289c44': '请在 ',
            'b470abb701b6657a3c037523627c1dacc3e79c0c95a70cb00540ccb9e56911a4': ' 圈内执行处罚',
        },
        'stopAndGoServeNow': {
            '43c2035964e7c82b5b120d9871b362dd20c9dd9bf0b15a90ee9f0aab44510fe9': '本圈须执行处罚，否则取消资格',
        },
        'yellowGiveBackLabelOne': {
            '90f03aa4a9852d72905f17853bc312a91e7b93b9bdaeb2253cf3adf81e2d99dc': '交还 1 个名次',
        },
        'yellowGiveBackLabelMany': {
            '9efa40d33036cbc25c36d5a491bb7f2d685df8862effedaf5a699c8ef4b4171b': '交还 ',
            '3205f9e21f1f4520a163763d3aec3b97ec40ea161377233c212db3d87a88124c': ' 个名次',
        },
        'yellowGiveBackReason': {
            '41eeced44cb25fa8e25dc3911fa154420231ca4bb3ce8122754b9178882434f6': '黄旗期间超车',
        },
        'yellowGiveBackWithinLabel': {
            '360bac1e6650a114ba2cdc216aacb11c30e1f7c714934140a9a66db6b1005985': '剩余',
        },
        'slowDownLabel': {
            '48c8b0968fc99d951c09b0a8c5c10c2b44b027a3b1093af954ef3d821c32071f': '减速处罚',
        },
        'slowDownGiveBackLabel': {
            '4447faebcc9b8410e678ea432114507878803c185c9055a314f22c18de683ba9': '须让回时间',
        },
        'slowDownWithinLabel': {
            '360bac1e6650a114ba2cdc216aacb11c30e1f7c714934140a9a66db6b1005985': '剩余',
        },
        'trackLimitsLabel': {
            '84975a499e86ac6f25d848d7804117685e9602bea986b8ccf8494118b75d6107': '越界警告 ',
        },
        'trackLimitsReason': {
            'd1d1aa8729d95cd8653340dce12240186847d98ad1f0c1a51fd57d4fbe80ff97': '超出赛道边界',
        },
        'strikesClearedLabel': {
            '4247ee8e0ac488dc70da0e1f4120047df6ffbe78947e8b36fe939f9a0f884859': '越界警告已清除',
        },
        'strikesClearedReason': {
            'd1d1aa8729d95cd8653340dce12240186847d98ad1f0c1a51fd57d4fbe80ff97': '赛道边界',
        },
        'timeDeductionLabel': {
            '9b4498c936b4f32b21daaa21ed2d86bba45caac2e4a2334771f48d31b5638d57': '时间处罚',
        },
        'incidentLimitLabel': {
            '00ed81a3807fbdc40aff5763671ddb041637e2585ad35a806a5765016b761088': '事故分上限 ',
        },
        'incidentLimitLeft': {
            '294aec9aef54360f98545cdfd14bf18ebc66c1d2dd5acd8c5e731214edbd2f16': ' 分后取消资格',
        },
        'incidentLimitLast': {
            '08dfecb7b2abc9ff7013e1e8d52219bde29d984edbbca32b21724178eb59f7af': '再记 1 分将取消资格',
        },
        'incidentPointsLabel': {
            '6b1a3c520ea72620b954cfffe56884adf145dddaf0c489be582272a7516131e3': '事故分',
        },
        'editMode__label': {
            'c5b7cd6e4ffa05b908b498f9490872c0d8b88f9669de3dc9fd46bb75063c0761': '状态提示',
        },
    },
    'mfd': {
        'pageTitle': {
            '8e99cd986fa2ec261c93d7669c1edfb2477d3b6355a6fb4fb08be4deba52ae2f': '相对位置',
            'e8d08c77c81a458f35b5eec2340ba18b1da647142ea258fc7c943a335f32af28': '进站',
            'a62394ba4acc97cd00f78b57e4ff3a1e623525529df2981dea2a3650ba56a77f': '车辆',
            '74beb729e4ccb757e74413e04c569ad3040c88a3b3dc18351c130ce72b903dbd': '圈速',
            'ac20a57bfde0bbc40bfe70895eb1cfacc944aaff06ca784053623c569b3e1b3d': '隐藏',
        },
        'tabHide__text': {
            '0c944fca9b62a9a163cf17603a8c44c3b7dcd2dd8186fd09e3ba007bb02bba18': '隐藏',
        },
        'tabPit__text': {
            '24c32f8b97218e6ae946901ea6e3cb2a151f94e7686a6ccd1d492cd76ad02a83': '进站',
        },
        'vehLabel0': {
            '6ed1ec7671be0bc861067da7424bc1178049f037d86b2e3607997d729c0d78bb': '牵引力控制',
        },
        'vehLabel1': {
            '831a73a68b11ec563ed784643d022a9f3cf6ca0ff7b8589ff50622c7d3cfeee0': '制动防抱死',
        },
        'vehLabel2': {
            'dcd283bce28c457df7377f798aed7f3bed1447c08aee193ec1b7f78f55d01191': '制动力分配',
        },
        'vehLabel7': {
            '002224876c15127a6131d3244ce2248bb7cdc20b76cbb0cf6230e2534ee5e05a': '车灯',
        },
        'ffbLabel': {
            'fe1bcef174e3c70f2b1671b900a170541481725a76e20f7d8cbe0a6dad54fad8': '方向盘力反馈',
        },
        'pitLabel0': {
            '2ac620c6a7e03d42cab0d35de06aa6f698120cebdc73e4b5828092e5633cd2cf': '预设',
        },
        'pitLabel1': {
            '342593b11f0d3345e6f8070346ae73360c891ed994629f2ffb9902f3ef9b5f8a': '执行处罚',
        },
        'pitLabel2': {
            'bbb321d6e8939cceb4fbfd1b5875ac94b92a67b887c70d8f5813412b4ed1b5eb': '更换车手',
        },
        'pitLabel3': {
            '0904608e24923574cd745c05816fe4f92ae3d4965a087586e20e1db1cced5b5b': '加油',
        },
        'pitLabel4': {
            '3f8860fd98673743e85d6abaec9769bad2dbe7045eda451754efbb15ba056d10': '前轮轮胎',
        },
        'pitLabel5': {
            '67f5c01a7fb1b9305211f7386287308b4a35255b33cd56b8aecede8faca9da3d': '后轮轮胎',
        },
        'pitLabel6': {
            '1e245b10382b279f391c85bd53dd668f659fe7dfcaa5ee0594fe8321ce30a609': '车身损伤',
        },
        'pitLabel7': {
            '2e39d2a18098655454842c16417a84d8dd8b5d54085bca420d73c96a02f0b520': '前部空力损伤',
        },
        'pitLabel8': {
            '1592d00c3e880fe76cadf69c774649ff099348f58fab3512a80ec569e940de00': '后部空力损伤',
        },
        'pitLabel9': {
            'c41e90f336876d708a036538b36d67975a48c62956b46fd167118676ae89c7ff': '悬架损伤',
        },
        'pitValue3': {
            '48532bf2ba4bfa0697d805566342d6fd9283d6f1cb117dfe7a4ff2d79898163f': ' 圈)',
        },
        'pitEstimateLabel': {
            '6fa34c323d0c66d6559709bce91b80a5f1e0a06d1af363eea0d5af3624d7fe3a': '进站耗时',
            'd8509e57859f8772176ab793809b5cdecf2df6643256ce62727072531c7d820f': '预计进站耗时',
        },
    },
    'standings': {
        'sessionLabel': {
            'dc120be59da2cc6199caebaf2305fd5c5925bedf7dc1fb499e1c5ae55775c07e': '排行榜',
            'e7932041b7015d184f77bc5a4befcd13a1910a2735567c087c89afc794135c09': '练习',
            'da2e352182d0d8a261a89cdf88fcc29057adbbf40fbe1fce82ea2f709d530629': '排位赛',
            'c51fb9b52aac0ff0312fc8e2cac230dff0ae58bfc0e55dff9510beabd0f642dd': '正赛',
            'f75654538ac7123dcafa623ce88bb8f24b6e12bfb51ec94edd5e2a787741f221': '练习 1',
            'e02136393a1e8e738448ed62a29741f3662010602a77a83084dd46ade4032033': '练习 2',
            '946e679c10f10c0ede5741727f9ef47d58c6dafac53c4169a01a6e8a1ed2d087': '练习 3',
            '4726e395ea2a344efb1ca3cc304be261285084e8b8718ca0ae8da2d8dc744315': '练习 4',
            '29a7fa98fe258c0239a26bf0c3d8afa4273cf8a006f5643fed34e58caec2bc97': '排位赛 1',
            'e9fc2f1a2c9cb1f4f4138d2b761ae2cc2ec149d3da3ce8bf331a0855869edddf': '排位赛 2',
            '4435af25d71b04afc43d97b2eb70013aad43f219380354877a0ef388490c3c6e': '排位赛 3',
            '8b6504c028fe7f0fcf34ca51c696c7e7650e834707ad4ec5b6df4ebd56c587d9': '排位赛 4',
            'cb25f11495efd161028c74b85a36ee21abacfe6b5d0680d0078c07a32ff96f8e': '正赛 1',
            '068a2c593d6ce3653a159269e4797bc7afa4a502ea57a524f5bc65b3371c940a': '正赛 2',
            '5212419e46bbdda07920b7e827df87fa0cfb3193b10f2adf9a9b5615ed7cbc97': '正赛 3',
            '7e25972eab913682d73a80982fe3c87cc6613ee39b1253d4bfd461d1098eee36': '正赛 4',
        },
        'lastLap': {
            '20797ee0657b01c990353bc9862562fb29998b8b26a69d59c5db31cfc42dba26': '已完赛',
            'b2c5db59a7a7d3aac12210eb0c4293993fbda9d3f68e9c71704a190001ff7b1f': '最后一圈',
        },
        'lapCounter': {
            '4cbaaa222a302d448bf30f3d6b68b9ec72494242e26a4499f314f9591391006c': '圈数 ',
        },
        'pit': {
            '24c32f8b97218e6ae946901ea6e3cb2a151f94e7686a6ccd1d492cd76ad02a83': '进站',
        },
        'statusLabel': {
            '73bfb0b10ea6b04af39c2bad20d5296a9e1fd6f844dd78a91553b217eae04aa5': '退赛',
            'd03133c2558b769e22139dbab9a3658f2027aea9738d90dd0ae067eba03d17ad': '未晋',
            '020965a2f08f402892237071bfe446f66ead0f6d4eacdc6a12981a402439de58': '未发',
            '626aba2d8d7ade0098552b1d4ef097f2b39ec5de7e9fa526749f974e85351d4f': '取消',
            'a8b5666911be2d26a16e7592d70ac6ad363f7039cbe58b4a0de0e36857c84226': '过站',
            'd04c6baa6fa79ab601a55132b61c3207e74a94b2b5444afa7a483b70f2bf2da1': '处罚',
            '58d9e33c417379bdf294f2e6907c186c529d7691e73867a82207314837701bea': '停走',
            '17a0c4286c4f7d567d99f5314bc512eb146035a450da766fcb6e4b73b6a6cd74': '减速',
        },
        'lbPendingLabel': {
            '02bd349299173f7fdf2dbc983d70961b26d74e6260c3755a058e25f5ee172f98': '失败',
            '332011b91ccd9887592cd7072f12da38748e37ee1af81985f9c8e1f066aec6fb': '待定',
        },
        'lbPlaceholder': {
            '50ee7396a9788ab20ac59d57c43385f494bbf714c6a5ead4592650bae7b50fc4': '排行榜暂不可用',
            '0c5e62b8ad5235d18cd7753ed542243ca72f0f0c7eebe93e247e105c0985fb6a': '正在加载排行榜',
            '190e813ffbbf54de79253dfaa66f53d4496bab4160f42fa3f12b07f2158ae1c6': '暂无圈速记录…',
        },
        'editMode__label': {
            'ddf15407a6a421fb7849f121e1aa174080f71f92cf9dc6af700b67a7f46065d8': '排名面板',
        },
    },
}

# Option comparisons use the HUD runtime's uppercase normalization.
MFD_OPTIONS = {
    'vehValue7': ('开启', '关闭'),
    'pitValue0': ('自动',),
    'pitValue1': ('是', '否', '不变'),
    'pitValue2': ('不变',),
    'pitValue3': ('不变', '自动', '加满'),
    'pitValue4': ('不变', '更换', '软胎', '中性胎', '硬胎', '雨胎'),
    'pitValue5': ('不变', '更换', '软胎', '中性胎', '硬胎', '雨胎'),
    'pitValue6': ('不变', '修理'),
    'pitValue7': ('不变', '修理'),
    'pitValue8': ('不变', '修理'),
    'pitValue9': ('不变', '修理'),
    'pitButtonText': ('请求进站', '取消进站', '确认进站', '已请求进站'),
}

# Each value contains the full normalized label digest and its ordered word
# digests. The words come from the user's own game files at install time.
NATIVE_LABELS = {
    '开启': (
        'e8a01133b1351e5fa434167135400d1998d3daa8ce74e3dd9bb57582fa4d7b97',
        (
            'e8a01133b1351e5fa434167135400d1998d3daa8ce74e3dd9bb57582fa4d7b97',
        ),
    ),
    '关闭': (
        '38cca6bea010af8adaf4be7d270456fa9adef8c0252db91f2767c607d077319b',
        (
            '38cca6bea010af8adaf4be7d270456fa9adef8c0252db91f2767c607d077319b',
        ),
    ),
    '自动': (
        '6ea56fae9eacbb0ebed74bbbe731cf1179b7d41146162fe9b8c26cf0615c2367',
        (
            '6ea56fae9eacbb0ebed74bbbe731cf1179b7d41146162fe9b8c26cf0615c2367',
        ),
    ),
    '是': (
        'f9171164593756e56fb197327b529a4955590566560dbe62d586bff41be9d297',
        (
            'f9171164593756e56fb197327b529a4955590566560dbe62d586bff41be9d297',
        ),
    ),
    '否': (
        '23794d91c53ae875c8e247d72561e35d9d06ee07c70c9e0dbcc977a6d161504a',
        (
            '23794d91c53ae875c8e247d72561e35d9d06ee07c70c9e0dbcc977a6d161504a',
        ),
    ),
    '不变': (
        '4b5d1d23cc0b25d90eaaa7064474688861f698efe50f11f708ea7ecd41a844c6',
        (
            '23794d91c53ae875c8e247d72561e35d9d06ee07c70c9e0dbcc977a6d161504a',
            '7886016c640975f8362f7bb792dd26be3af962887943f1a28658d0c4c52a8fe7',
        ),
    ),
    '加满': (
        '79cb944d42c0a5642101f9ec9b51fd33669c1830cd17e03ee7cd04c1d515bde0',
        (
            '391edbf2617c1b7e5feefdf289959ccf8b01c49d4db657aa769acd4fb80818c1',
            '42cb4e6f84970e97d515b9d57dfd4e4fef5d482061b7d2c33179f2ad76495e11',
        ),
    ),
    '更换': (
        '7886016c640975f8362f7bb792dd26be3af962887943f1a28658d0c4c52a8fe7',
        (
            '7886016c640975f8362f7bb792dd26be3af962887943f1a28658d0c4c52a8fe7',
        ),
    ),
    '软胎': (
        'ac80053c0f73f9ff07e27adf3f07d7b94fb46201bb1a4a497f8aff75b281b6f9',
        (
            'ac80053c0f73f9ff07e27adf3f07d7b94fb46201bb1a4a497f8aff75b281b6f9',
        ),
    ),
    '中性胎': (
        '7c48dd672a68098c3a9dac57805004a146db39c8d60c81d091537ee9c4a76054',
        (
            '7c48dd672a68098c3a9dac57805004a146db39c8d60c81d091537ee9c4a76054',
        ),
    ),
    '硬胎': (
        '0e24076baf990d55aa1511d1af1d6741b19c9a2e9e9911f9ec7b5d5dbe5a5e9f',
        (
            '0e24076baf990d55aa1511d1af1d6741b19c9a2e9e9911f9ec7b5d5dbe5a5e9f',
        ),
    ),
    '雨胎': (
        'a915428c5f0d13ebd5765c2f388a30d70633c642957a0f7f02ca620bb121ae01',
        (
            'a915428c5f0d13ebd5765c2f388a30d70633c642957a0f7f02ca620bb121ae01',
        ),
    ),
    '修理': (
        'd90b7f3c18342b7511bff9e82efc1c2fc85caf0ee6fe504ad079f14d8e115942',
        (
            'd90b7f3c18342b7511bff9e82efc1c2fc85caf0ee6fe504ad079f14d8e115942',
        ),
    ),
    '请求进站': (
        '0fe85d013dd233b5c5de81e1dc150fe02fd39e2ed0b516364b412b4e1c100eda',
        (
            '041569db9df57e50ef344a033267abd8e60ac37c3afd3eac3c658b434ea311eb',
            '24c32f8b97218e6ae946901ea6e3cb2a151f94e7686a6ccd1d492cd76ad02a83',
            '04dedf8afeb8a4177a009f41bb78018af601e341ed4322d4073911c9ac879726',
        ),
    ),
    '取消进站': (
        '9617a11ca3b3b59ee982707219a71968fc6a08ee6c0446340fcd4eafaaeea175',
        (
            'ad8d698573fcb090121f2003187e82cec33f5596e4ee2279d6c6fb7b61dc0179',
            '24c32f8b97218e6ae946901ea6e3cb2a151f94e7686a6ccd1d492cd76ad02a83',
            '04dedf8afeb8a4177a009f41bb78018af601e341ed4322d4073911c9ac879726',
        ),
    ),
    '确认进站': (
        'b89cce705c807cf9445e116d254f0022e75704097526401486b2680c619e4763',
        (
            '8adb7edfc88fd8916a0ed2679b63f52b0ae69a9f042b6561b710cf2f7bfc487b',
            '24c32f8b97218e6ae946901ea6e3cb2a151f94e7686a6ccd1d492cd76ad02a83',
            '04dedf8afeb8a4177a009f41bb78018af601e341ed4322d4073911c9ac879726',
        ),
    ),
    '已请求进站': (
        '8a5d41942f53b3bcd911cdae1f62cbc8f7165d1cb3bd01cb6722c44325be55f3',
        (
            '24c32f8b97218e6ae946901ea6e3cb2a151f94e7686a6ccd1d492cd76ad02a83',
            '04dedf8afeb8a4177a009f41bb78018af601e341ed4322d4073911c9ac879726',
            '40bf66b304b3d092597141734ae48f3bebfad86c9da693bfed1c93ee95506aa8',
        ),
    ),
}
