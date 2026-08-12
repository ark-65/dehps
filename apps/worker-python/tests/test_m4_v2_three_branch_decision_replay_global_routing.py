from __future__ import annotations

import ast
import base64
import copy
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import zlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg
import pytest

from dehps.config import ROOT_DIR
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import (
    predictive_route_reconciliation as governance_reference,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    branch_decision as marginal,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    joint_residual_increment as joint,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    routing,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    temporal_marginal_increment as temporal,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    AdditiveManifestMigrationError,
    verify_failed_task_recovery_event_metadata,
)
from dehps.research_os.information_theory.progress import (
    M4_P3_PREDICTIVE_PREREGISTRATION_FACT,
    M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY,
    M4_V2_SUCCESSOR_REPLAY_FACTS,
    M4_V2_SUCCESSOR_TASKS,
    P2R_TASK_KEY,
    PREDICTIVE_P3_PASS_TO_P4_FACT,
    PREDICTIVE_P3_TASK_KEY,
    PREDICTIVE_P4_TASK_KEY,
    PREDICTIVE_P5_TASK_KEY,
    validate_m4_v2_successor_structure,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import (
    M4_V2_ARTIFACT_TYPE_REGISTRY,
    M4_V2_BRANCH_IDS,
    M4_V2_ESTIMAND_DIGESTS,
    M4_V2_MEASUREMENT_CONTRACT_DIGEST,
    M4_V2_MEASUREMENT_CONTRACT_KEY,
    M4_V2_NESTED_SCHEMA_REGISTRY,
    ControlPlaneManifest,
    M4V2BranchDecisionArtifact,
    MainlineArtifactRegistration,
    ResearchOSValidationError,
    TaskStatus,
    governance_execution_metadata_digest,
    governance_request_identity_digest,
    governance_reviewer_decision_digest,
    jsonable,
    m4_v2_canonical_json,
    validate_m4_v2_artifact_envelope,
    validate_m4_v2_nested_schema,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from scripts import build_m4_v2_global_routing_manifest as global_builder
from scripts import build_m4_v2_joint_residual_increment_manifest as joint_builder
from scripts import build_m4_v2_temporal_marginal_increment_manifest as temporal_builder
from scripts import build_m4_v2_three_branch_decision_manifest as marginal_builder

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
CONTROL_PLANE_KEY = "m4-information-theory-mainline"
GIT_COMMIT = "a" * 40
RECOVERY_INPUT_MANIFEST_DIGEST = (
    "94f7e6448fa1572802a050129d09c8bd679772afc62f31f0d1dc2544d098c58a"
)
RECOVERY_INPUT_SNAPSHOT_DIGEST = (
    "85be3d0edf17b94510d68da6b5b8bfe1c73583222a8bc2822cb7e46bee08f4e3"
)
RECOVERY_INPUT_CANONICAL_SHA256 = "792695388f9e0ce16db53c9dd092d3442816597a1a15dc0cdcbe3e2b15def6cd"
RECOVERY_INPUT_COMPRESSED_SHA256 = "62297ed91f320b6d9588d20db2230d875d4cf1ed5a29c18fa9dfa476b1d8d2a0"
RECOVERY_INPUT_FIXTURE_B85_SHA256 = "7304ef330aac52e311c22cea2e6e8076c0d3304ef49724b7a97c7cc61981e2a2"
RECOVERY_INPUT_FIXTURE_B85 = (
    "c-ri}X>%J%wk7yiVEQy;BjotL;L8|OVr8;R+oPzgu5K%X`6}@xMX(7{S^1vTf1h(B0)YSske~=ESyi%JL=l1T?Jn"
    "nBzkdC{pVg4A=FcYo{VZHwopyiu-_Ppo^0#oA$MbS^byhx?^Q(zq!Z4>Mr7Fj*cQU0Um=D3(S{Vym#KMZNEM#G1U"
    "@W`Hn9I(}Y^)I3%38e?&z?U!D<4Dpef&9`o}ZnbmvKEk4`<^T=7s)>2R^HD3g@%)(}drbzn64<HM<;#tE)1<3RkD"
    "I^9kpwYME_xifNh9i>#$e+DKmvmsZG}v^JbsqnRtFDr2Pb+Nc_Q)uwGEmvlPE>&6$ev(xnZ#0gbB&pI<MQYhIc8-"
    "$hkzpT;MRCzQBKboK_Q$|~6mEy@JVK5~uw{QJi!u<NOnYD46onKvIR>xliTAQDKJRe_{i?i_i<d?(aqdy%TzTD+I"
    "lRq85{a=S~Zhy3WFDCQvSNM41Mb0@^sRf45OVr+5E_vdHN1jr2NnwRDme8u~4bP@>pM;3g8_8I?wXsQHK^mL9&(<"
    "iDLdJVV#DtZ|Fn?A;NK&SWG1|n+L{u!`Y0n*FUdQ(B7h=rE^WV>}K9#G}G|u4)GH^A~QY%cittMIFy-BrllTFig1"
    "}ReBqo36a?R?BiMu+9bQZw#L%+73l`Q`OFB<}pQLWU+zdFh=^3Cl<S7Kv5WNteKti-lJu0?)o^YnV5TB_)-?x+{@"
    "l4b0u$LUk&M9Hch7+L8mrL|P{_w+Vl6OoOi4mf)(4H8W<k4_+qem=h+*)VCn823MDO{jcTnyqqmtz`Xj*f)SX3%#"
    "CFR{S`taiwTy{PoFerCPpb~-XhPXTAiwZ3_BA<-+~<f7S4VhFLeG>Ks)pKvLS9E|5<w;t=2XuAvv@Hs|x+Lm1WG8"
    "hX^SF^-)+KEv>0u)#91T(4)Q~((1F*c-g4%+H^_AohkToC<QOJn71r+QibJWT=rTAW{b0#JG?qWIb*>}<*EYuV+U"
    "=Vp8sb_R|UokngjchW}h$4N@F#oa9Hjdc!(v|Qk=`m<QP*i+2;~1q>fkZq=LE!mdMDVVN9G9SW4NqqM>c`fcKuBf"
    "4s3U5d5Mn6i;QFO-`Z4U{t`{VI{M0P!w1u<+HA&b1uO`ItK-TZDE!#b;Cfs>gDXe%K3OcyS_}NSMCa3hH`jcc+t9"
    "OhkueSKBUU5WEFy;Ima+DrL^YJM~Ip(DdrL|rj;f>hs%$x1wK8`G@yl|PjXT^am56QB+GcQw7fzUgiDa$z_p7O19"
    "UKjzDlVi#wQ#L0?MVFU2SGyO1?l2aw`V?v;|cZ469T@MNz7+MVpeDgk9Ax1s#-*5zd7hrz5OOgb%6~mN&`}v1lue"
    "U54K}$I*z|CX?GdDI4)XPvYs>>D87;F3RQUER%+pdb+fOlYovvPGZWQ!FJeEAVAKGkQ}+j=ork34Vo3hWW*qtlGJ"
    "&YAQ#p9l}6^*Xl7oT1z1~cEvv_**zAQ@D%Xr@G8s}Ip)@fk6ESNw86Ts!Hd_%O&%8o!3!0Kcfx2rEU^zmuridb(7"
    "7}eTn0XN)q8L>y$-w>!#chrP)1Ngrq~{El2Vzo}i(prp`WUXt)>ZKMpONE_v$I@it!lX}=c#Oc5QgLG^m7@9>x|V"
    "1m#0^sJ~sv!^R@L$-IT7Zc0a+qU`9Q>y@rWPCBsBoRe3UwMF|g+JkvVCqS~y5g<eDAYbwxVD}iq6pt04?VZi4Thw"
    "ovgYECfo3AO;vK<ON_Hl&LNc3i`@aVISF)+mWd4?$rWG07>5+usgXULXrqngAP&ere@kTJW-Dl!hEQErs?aln8rZ"
    "17RY#XSkul4AbWJw_}VI?ll$x3jz_)JQjo5fJ7@FRp40p#9;8?d!6^XaDh?4Hyc<eHL(5ZY(~;BdGYr3yH|%Nhtt"
    "0to%}pKK74m@bUc0g;RL@w>>oabAOMY?hHjk}IBoL!@ZkN2<HOg7Z%(E!-o80GK6r7mc**hMe|$JP9<2QOTP`44X"
    "Qv-OT@8F_Br&%NRup~#{#V29!~_clOAJ32g(%#Vm{dv*y2c`qq%Z(eu&zK2%eKxhuCFExzh({4f`hD~dIyJ<VUm+"
    "E4!Q_<0^iSy@=n8EYG5K&VIri@aImKIuN&%4KlpB(!#Q~W*Y_ufuQz@T+7?bP2SY82d-P6ANLVo%B4HiGjByBN&Q"
    "JkZQXpDLO4YiuV(}DQZPXAMsrAN206SMT>azTwYidmixNIk(Nm9zf;ne{CYAyn@2kmmUh+Ik%60iq=0x%S)QFs6r"
    "V3|~w@TVKb?D`4~m4z5}>O6sw!&)Q&TPRcl7|j3$B-sFVRwQ9DN)MYUs!dvYi7_R`Vc{Gz2G(?~8GwdOfOm56%fZ"
    "pBgCAclC6stb8GpgT#4{M`63C7WAV9E0IWo|a4d@)8t0O0Ap)~LUOn6oe5RJ^}EzlS%l8{MZf<b;9U$)bE1@w&YQ"
    "n*Z?PQR2%rs?&-$5NPr(ZNmu4#Vtg!2oMLkrK>83@{EtRN)Jtm`W9<s48HR#rp@=bbdC2ot}LGm<h1HOM}_XL17R"
    "E7()q`U}W?q>);{>P=~Ytsw-$vA&>w{#u>Pwi5R7c7H%9Jv)h`yEN7VVG6whixXlY+j<06p3j<ZSDCf{>kjIX(9U"
    "s0wJUD*w^Yq}=tG9nSd^vr0{Py+RlcTq9ra!)V`{K|2J0z(;eE1cnZ+r=HDoe$BdGON~BeLOJmjzRj(9hO$c7h1S"
    "uK*}u!El}l;E2I`YZyVpQmHjoA+*il*MU~6z?D`a8On!hj45H)_Imr-e*r-B`s`{P0Yw3MuP(0>L=j*P$fwcB_Jf"
    "b*ya0C-i^kuEc>n%y?09T9^5V5hFr&i56*?FhAn8!N@_<7uILEjFzK#a;hC^60SQNA#B!!qA@Y6k;y?=Mh7jguh?"
    ">{{&my4c*SVUL_1!Iw=1fJ9xtd+TF7@2Ja5Tp#uNifh){FG{u@O1)g6a+5XukXQE45G)fUFRJ-AtS7q0w!TVU<@W"
    "3U51GV^p-Ay!;^vFB}usG5G5oNL{?%vTvfAk%Mi%R^6?a(tO&dnRWm7)g2qdjSW_8ZYe51erVhRFDODL<P$0c99k"
    "LX7Oj&?DVEv=}+V<C{ZtYW5Yt=ky2qIx*Ob;Ydf$PD6GazH*lLIA!no7lit3ye^OGc6P%`E%PZ#9L<lpPSSb)X<Q"
    "7(kr_=@pse8;Bm{r4YpTo*+1YL&#uwib6)A@Xc=x4ljabP_WGse{va;B~gT*#-d8*xCbCj0Qw44TcGj6W6VxrVPQ"
    "+!x55R3QJ<$z%V<^yv|k?_|8(@`;MMf~$-&9di#4md{9cEGK{ZSHubYNndJdRs0#lkh>3oHKhkk?7g3c<Ux1QoiN"
    "diEi_dEbPz~w39;g#6J*DRY`hh?kHuY|g`e`$&3HblsF`C6|~6L^m4kH-gZUi^Ice){g<{rj(Z$>IMzeDUGr=G<<"
    "0_QnL;9Dt}Z2Ze&`mqn?Vs<u%TKy|nb4&Ey=6B?dffs+uP2s$}1WdQQTx3{_8lBwXzykMm=Je3bg8G@?;OYE@9$_"
    "o&b1URLmq3|B4K1@moviK^3TrTCuvsr|Wl80Ie7`#@~jS&48vA#h6IXi7Y>ijfc<4vdM=|+@M?(=o`cvl|}8Dc@G"
    "K)JYTkWr5teti4k&C8o#Yhu)CIgk~-n&b!{L%5*mP(lD?!i2+w!0V)xEws$AAQT8_@DgOd8cBfBWEbI;3g6n^Mm3"
    "%QWx`DeZ=jlx8Q9_o6kbdM1##6Y7;wWa@j~W>1ZvFi%8CQKdC<N^$ZJD$pGr8p8W^3$@Tvo`untTxqyh^70B$TCC"
    "(kiB4@v-I=4FOR8E{1iVz40Gi2?h{n%v#(4Z(*nf)hcj0p8g;SD7h}z%QD@w2Fe^Ciuis8Tc2b+X<y%R$;0@U~Rs"
    "uwHt0%*9a^VBGVF{%!P!dw7~e$%1Y4~rwxaF)=Yx|q>5>kK?cBjkSo9*wY@?3h1q4Z;juczkeL-AP>d(=ungQ0Ds"
    "4(ItwP3MT#~>g0TeSxQwk9}5n~KRD7dTJ7I4|(0-#Ke-as#2y!!C|=$FHtzPLU=IWwt>$FQ{v6%YjQmt@L$thC5g"
    "ILv&exQSJ;GoWP-w$CL4K4JMH)^U5IO)zQE9*~W#K5I@;B!P2h(7#Za1J=nL1`<8s4%!5b12PpXML;=-MbsG@w@Z"
    "7i{fFTXd3MnZ_8~^)=KEL4{w8m><CmB2XcZ*w{)T31x1iMB-?9#Lb|1|aut}S57II<|_-C~-sY+}X_%dr)G*I~rN"
    "DE_{LB2Qu6FjMvPDmC4w12yrZ`|J63`B1G>g^Ebwr{Rk(Jsbwzpw5hF&n;k4{6yDSGs?*-4`D);?*}itpE3v(G73"
    "dygR$|ch~1(1$o}<6%U&TJax~xSdoA}5+`YI07$XWMx6%A1fj~p0XBm72~At%E}P6u<uyoW0d*+~0M-a&EbCpZZG"
    "jttb`80Mw<Bz80iUb^f^oU3%8QZk51aw`&<2rq4sh48?6Nf`Xa=IXW3xAL01w7mikE`nft11R$mAo3%g@p|VS~0n"
    "^!T~px3t|XVW6@t$pu!cxU1c5tlKF<Z`okfAl;hw+rhLXh(ZAJi3$!M6gV;9DPSSm+D|+dEp-ksh<6TmnWfO9Rj_"
    "rDfL|Ce2W1W@5C;%lT@*Yn#ZP1fz5?8{LRZS2sF(-EAq!RevO|MgR@TrCiBQD=OVj|mYrugjyf%v!kV|E5OaUCKQ"
    "7A$@$`x=XM!W7DKHu!#@{Pp>bQRH>$bnZPz$)mzkrD*VD1-m`;t07ihj|vX2d9|kpit3g=R+*J40_A@QZ|4qN)w("
    "7uEDiA#Gn9<Y$~Zq*q}&CO5SVDfzNrs?AxG}(poIZ!BzQuF{3a_--U-VtX<x?+v^r-KTEr{c^7nbXJJXeCaOTRfv"
    "SBGGOGeSV6yTN%)|I3L1-Kx9(XcXEEot>RSH-Lpk~+zuxc~O!09!Cf<)T!$+{NJ!3-k6AuwT8GG(Ai7HSc+Q4l@D"
    "li(7eS_7pslP;&A<lDxxWnXiF5**eL+**W`VK)ty8+bSYxCZSpfKWl1DCCm_PXYY|wU7#+UNAwO%@Yx-5U^wzqlE"
    "68nqX{2DF!@809xZ~p7NeT2H{6ruu)tx=u;I^`WWvuibc$R7U$*iODnW%Td!bojwg<eGw)2LJTb{Y_cTS_pqs%lP"
    "e31#Oc-#2M7tnZL}IrJKTcfsvPc8G&Y<+t<l><Cps$q31dbI1R8f0Ebq<Q}Kzs}Z*{I#ZtNE${ZQX=mkRwk~LfXs"
    ">SfP|@v&_SqGSI+~tjkypj;V#Y(B3nntnyq|^i~)>0k_Wv!)6M`lTln$%H*o@8MYZ~Q3RBnk$I(-6sE%4Y%32ost"
    "A$TZ8+ijYWBIYE)966@IK7U?DA>?nF+SSJq2&7$~u&U-snghoS08V{tHG+NyvldmT{wC@GMtkTENvNnH34Yj>Qrc"
    "gMpLH4r^<&fX$6TdQTg94ED!pbf0{$b&y8}YYqRNcN;(rXPEhm+5EKG^`HS<%zi7Ev_kWV1DtS>ke~uf(pIZs{*2"
    "X_MoT`91shnz)QPAB1JK|Uq6hc)5;{`U#NvN~6>kd0Ri(DUYTy7c1bA*Od|;U?m{~zA8w-*m1H-ROMGd~eb{xcwq"
    "@!h`)5Nd<Rj$Sb4wecnH<SR@WYk0s_W`=f9c(xVD_|04FJa=jY=W&aI61Kv^2Oi=Vac?0Ah@o&AX4^~GeN%st!57"
    "DQe$>Bd=9Ue9GsY^V8L!f7-GY%A<s!+aO)Kg)>E>CNK#nle4(^FS7Aym(19<o$IJ^By}&9t3@8EORUjWV;lg^Xj0"
    "@ztfLtOOR0Rs3C{xq<M3EYvyb?u=U}1~l`JGC%J7YN8QOOs(--9vDf1ksL(U!5qs*`+F3#7^+yO0UERLUwdK?tsa"
    "A}XLG)I>|5MGQAOEtIap=?So_K$k6r4=~-37{NVxf5>Qo<^zg}f<K&xnJzkJ22sUgPzVPe$L%_RMSj@?y;C*9$}@"
    "lwzys)>D$-%@D7uvd(1?R=VWiu!*bHxGYk|#VLXdNtptryeN*8CP6w*`rj)+VriIs#Jz^6F{TLpk9GC(RUwWd^FO"
    "bv<Lj)rKN2)Q}QXi}trlEQ#eVv4{&csB+G!vbK%VC^j>b$LRQkn2)Sk#H9<CHTBxoUlijX)9oanG+f77UAJC9;eV"
    "H?e_yHD$anGO0zZXEj+4$<Vbi%%*SrySV@MwxSYkZNQs=V03aVFm<)g+yp-j@1%^c!4kogt0KL$`C6lxV0U(uzWv"
    "U6#g@G_&1dwT1F~hlyRg$DbZzF6PS71ll1uRA+@}z-60;MPbn=nIJBR<Qt(+KX~Lx#%QBn|L@CPj#Z3X&24M;M&-"
    "IVT|qkraS=Km{GiOH|2i%|tTT1V2a-1bS4x5GrNZ-UKU!X_w5xPN|ra2OWtF;%`KX9GDrZ4H@&`E4vNj!8_YPN)U"
    "hu9L*q71?Gn<3d#a?Brq0uDo))2JhJe`0{;VibP%fw4gseyf#xR|hTtHr5Tug0fy7zGN&>8`I#Kc{CW-Qn4PFCJ8"
    "WjU4q)9d0?`NDhw~rYmZ5vHGV9=M8Ljd!E6oPOP0))xb!db9W*0^b~I9sBC*O#!lN=%$%a1aUrl7l)r1ttMICow#"
    "ZwI`-ycmnl+uky6HtRzgbwy<(STj16G3~W8_P~oqn1Td)?u!T}uQZ3Hm#~cG?OPfNZM}lxM_#wbtKw^lSrhGks;)"
    "w#VOJD`CkQrDLToo`nP|832C)_5fX!Zuq2>uqVt%5BU@Kq}*yRYoBUOVq&0%!RGCsWAV=>o1?;S+6zD!_wSMYD{q"
    "NEls!4+a5L<n8fWtQOOHqLT+{u_R6vmaICw0mCQ^riW3s1#PH<a^{c%*bGbz?70X0Hlie7#e)WOV}I2E9YJY;{Gt"
    "Zl%Yg4dB$;x@z_j2l;iD-BmBA0$ghc_?ED$%CHce^tlY|utR$B0!Xh<Fvpc*+J9V)B?EDY0FFV1;}ghG6k1RemY0"
    "8Dk#nmr9?`31;+dz64uWZ}{c(4fY$co#Hd#7O|w9Dp$fUX=#;0MO;YB2ELK!3rAVYAP@<hFFWUU|Uu>j2D^(tYhf"
    "h15=KSUxjP-5U?OCj09{DXc6CSMEBb`&>DPLCom<TW8iR$C32iL-UMWy1rGi201kn=4!rImbRaeqH<uV3accmBnt"
    "2Y95?(+{W2BsUUnt$%1k8-XdgIlRgF3kEpgn~W+8iint$Q8RV6lL+O345zEGmz-VZk%NZA=l=NrDsz%Hs#baqwE;"
    "J@^Nv3d|8;8Kews8`xM%crlDHM9@kA8^Ame14kKiq<EA?N5L!?qLPv|8Nei|Ffd`S<67Nj37pZv8wt^mMu1~QQ*5"
    "Gyqu{_XVf8Zjzrb<{Xr6>_Fb${#I}v0FHBYM6xqyo@9ifI+x=7ov9FPv57A5JVfFRzKptzVb_zDlTWn>a<4rZ@oT"
    "Q}-3tbx*IEZAp)ABO#n1voeZ>lbe$1T7`-QwcQzgH9R?!v%Z*>^I1an`jDo!8Cw_O0YFRFYSP@0}LbSFCzrw3I%="
    "ub{XZM;oWeJMe&jWI=*gnx9tq&3<>}hi*#5F%O)hKR&+4D=vb;`Ml{wDW27BV9t1Ebz=GshR3LCL07{JnWHi8yJh"
    "QARE|3-ZY}im3SQSJpvP2DbMBAD0TrwJ<{-}VH{lkZ}=Bx-ESZ1oH(+NOH9)I;dGB`}MSZI42RH^E03^Xe#m=#DQ"
    "<O>`&SCuCo=F;Ima8Lm|!J$abXwP9~D0qNpN=%p}h_E8p0PyPruoK3sRMF<)BU;~2sT7Uj5d28#U^Fge3FI=MbZH"
    "}z*K7bB7{p5hotKae(KPRYb^sVA22-tIJ0qQ{i4;5l+K@%TV1!8eC0+FrN(wgsK?afaoZ>bh-VAHS_Bf=*v`0Y!C"
    "5j%g5;^=Lrx-YtTSY@T2CxADsU#jAo)=V*XT_z;3C6&>q$W&Kau56$ObQ)ia{&~9BF=!q(pCe$A;5fz%A^8A1OgA"
    "&tguX`R*34}2DJPNRtH2D65v6^Ex<Tvt|qby-d#Av#zp}Jfwu**1+iAJ@remKZy+hpdy*(*Xft!V+2kp3xFAhU-g"
    "$|z4YWyYEPNF0TL?OIR|L3~tpr0t;13_u>V7D&L-s`#;36NP+zvV$crHaMP*LWB%M~6B4hVn%{5NLGmV}F@6#L2m"
    "+JG4}uolD-T~C2=P{3HT2ls+gf+dH~;=oRDQw3g-@`5rfqiTFKOM4s8x<1K>#?TW901g`f0s>8enS+8S@KsL<v<?"
    "6#Lf#}KF%!Q8Aq-@MWq|YqO7Vd#GFIv28^ns!sS)P@?qT6V7J(2k^bgLs61|V$T##L5fne;uN4ETC7NqHD3q}eER"
    "Iz|rP0qkmWoSPDHdCNjMMdu&hsFy!SU`anZeU~TqyqIOf~t{oZ?udJ^kt0GP6QSd0>J6?hY}pP!V<fYaCCIo2lBr"
    "Yt^c}R?Gzy#LW36o)M#=j3Yw;}C0bvJ19Hj^D_}>N;DATpEzjK22_I3!L{@U!SXg)`M#qT3U^tMV!_r|{fXpGC(F"
    "<#M&=@Q%QUo(rSpmzZxW7eP?zZQGIfF}-867DU@1>KLkWS|$2!Ei+Hd!<S(F$|`73SGy+C?w{v`J53{cHwWhpz^|"
    "BF+IX04uKWQcs7nEU0c3m3H|QU_89F1kug~HqvLY*D<YY8PIlZ0xGiBLOTyy0M8{2cufWaU;yK;!0qG=SPg(k03w"
    ")x#NdyZo=Dm!vnj&WVIhJ5lBb=a#K1p5k#$atqVyUb5FVNP3KMK?P83ki5--^Q;Fe#eyfrW>YA(b60(;WQA3CWBV"
    "FaDTa%H$K=`+BEBSMDHK!b$`6DuiAXzu|GMw#efKp7w{CWH2mX!8W{7QPt{n34*WA(iA-&>px08Vhh|WuK#4*EP%"
    "~otjJ-UsMdTPeEhA>;hQPBn5;FX8^Rv!O`g)ou~8VFoaUT6G1LLyhU)1awO<DI8YRH&eJhHWytL(P)lyAb`;boo?"
    "8b+q?1LGcHP;osBjaoT`f%jR__5K&@AnXX!23e1`8ymb=1H{fa8`hY;px^W1D%WiUNuDFs+*~I?@JOW-0gzHB0ak"
    "j&{E|3{v5M_LQp^OE45vgh+=>bpsqwSqR?n2ajX|gb8}epe7NlgFG_KEyd}bs9;12mKgR5<1ijnR>DVV5I_sV4+j"
    ";rns|CzqqDI2ijc60WHIq@rQk9hdCU==hj9n)2Tt~Z6E;y4NHl)OA#6E;J*lu)Qbjl=P*H)&O_sA}dj+^nF-h=@#"
    "VCMYQ-BXGNi;PK0M)B4f=$pXMTx0k`!TBk-LJs7HE4z<VlGo$5YV2o9H5Sr?~51Xw-y$aFw)m`fBggkgd0sKO3d{"
    "VEn1j0E<#NpOx058AP^ddQv~zLUNk#n89o*?-UrJj5ulvlHHYIgo(>EFBJxUGbFlR=_*#M~R+lh27HfrpL;>&2A^"
    "?*R`d-7>cxD`wnv#{!3?()-8x5Rx>L3@1!a{Vq3v>-W52gzWVP$~A&~CI75?VUZ6x!1crU<B$TRIg3OJ$1i75br5"
    "0y4-DL)b-5TY(fu;wsU$KY#)YI}c&|iE9A^C<{O$BY#Gb0tFgmiEC0=LDG585Ezt#aJK-N&^#MQjsn<0hY1B!Oiq"
    "Spn+1?5ZI8K{pwd7~B6@J!k~F?0bmmwUXRReU1Z^VLcV|#&v0;H}rx;#1qco4auu4$4`63HsKpl!O5y}y2<`SKfK"
    "xTkx-V%zWeNcD?PCN-{750+@umNfV1wpuI`*>m<Y!I+(4&b1K%RquK7g!5NFOp0}DqErrZ)`!3;EPyQ@Fm*(4q<<"
    "Ty5UJQ5n}>0aO*z93{_0L3(}}cp<$*N4781O7*jZ~nk;EY9!^!N1kMc*fJL%E;g0H=u;M&iWdMhw6D0}jXfsrWF;"
    "}T>LDg2%wgBu3ogak`?Qdw^7C?`0uw>CiLADIsx=>P?$MQt@ibPfkN~R6`1BT`$Kx?KT5fEpkVjQ3W;75Uzh=IGw"
    "oFuHA76CAvk^%zOhK}kHS+uY*kl;c`a4{v2Wdn$i%EN{>*u*Gb!r6732eXL1S{MsVAlRtKWK&3(3s^18F%%~$;F<"
    "uYZb1z|jRbTAMjej<5;$g(o(SlDlhEd)&;SyUI66}&IncOPg;QEn0llo2Dg!WXO{L@H5S2g?UiBDbTYej=ED2|+3"
    "T+S`>x7A?eH0fBF|`;8aYc<`6O@w~AXCE#!~TOAL^08T5lZ@~Jv0yOHHrY3?I}BmoDpp#GL7$rh_$7ID&X>%3OG|"
    "!z-{?s4DZI7yvhMNoq)du*|D&jwNlj_I%nZarh-0{JDQYr00l`$OiIHVsPu`0-=yps*o?|`p!yuJmx@E}zzi9Tkp"
    "R6{jE+jfvnwh~rL&?88&CNT@Eq(h2Dz?;+FQ$lgX6OBV%hpi0rdbMOEF^D01ewtUVylP(1|&o0uTaBB7BIW{JDg+"
    "GXUmTr&xh^F?@JH%9el+_ZnV9JI#2a*t)bDzzehH$j>OynY|5iv6F}q7CIY0K0Ut*zm^G|xCidEIY%mb#5A1_VnE"
    "YUFikt#u!=mxCpNZ(Dm`#$txC~@)B<-+sBnY9*O{WQCv2yN%sTjLcp0irWdkvN)tqLP6#L7JI51pAfsuCdej{9D8"
    "}vK9Gf?@{FSE7?$9cJ&fDRQpI9-6ML!pXHaJ=X*@LC071)M_TpbNp%A(%kB+=WUUG5B_>L^BZ-=~o68mv#=Ic3EI"
    "WN&-SA_N8*r!3cog3KI%O$RVI6DLUrQ0pIQY26SHjezm&&yS_rP0IjMf6;ROb3luEdswrOVHRMXd%m8}9m4hh?&t"
    "#Q}G8jP`U`HL;lB2yGBVqzfu7Th#%N9t}f-J#h5G03hqbduLm@mvS##>=HwW#&(i1X@zE-q)EXRXEPRwP-fc>{Y5"
    "NK0vo8e9jOB3%S_3YEBxSGfjYAqKpvK}Cfm5GjFZL*f%xpl(=3347rQW+mEO(_l$j0XjkwQx(-Sa`^BTDi<nJ;^4"
    "Ryqt@;>fPvC13hlKCwwI^#6*CV$2VR=#KpjjQ08z@)V&>s@C^iQ>&w$q9s%f8vYKE8ubmc%iD%Mg1vjgk{elvI~Z"
    "M|*KZuE3ioYGmj#Ojpjo7!L!9|<~04Nz|&yTKK=-*K(m_mUDF&ZERBER77QQbs;e*P19x5Xt}->k=Kl21?3Q0ZhR"
    "vhzf?{!3#~HLSdBl7${i@OQsb?(qJvP;uic59FX=@X<Jy)(E~>81^_b_z!kUG(XG|7fY>vzbcl+j%)ml@fJ*C7fW"
    "sXOJyl~2%+py(K}Ct2p=vPJFeP(Nc>?*AFmFPTBr+Pmcfo?K1N;JH`3j6Ff=Vt1%5+Uuz>Y#xfB*nTxcKV9EtCJR"
    "FDQ3)0jansg?UmU3NbU<5dhb=0DcN~0tf=&&{91fqEIl!K<E?)$H1XZHq-e9Nm1NFX5ABN^gv7kcp3aqQidB8P`l"
    "V1n3N3mgp>33upUJMhL`<~=ti;&C{&Zy2GIal%)A0Ua@d3l`dS=q$QYP$APM*rFh}B?7%l_bF;dh(qAZ)d7oa96B"
    "5mjbgA_vt$1Uw4B-ll&{V3oXpk?r3Sa#ObWTAZJuO1o=r_Rn!X9J8e@!%Wq@DMM>e4%tV4}5MZs_%kQJ_pcolZl#"
    "}4Adhn<gikTw*rDhZ)5<9O^HyG1W<xHf~k4<D!?kN62J){N|gYhw2M$doI$b~$8cy*JJ@{;XGtzS%{#E2^`cPWr|"
    "g53IYxqqC33hB!bugQ233~<{*tGdxOOg64W)^rV;oL7*hR|Sr;LkIEZzmpgoK#_ETp}G%)uo=rm^6a3Qa*03RVC5"
    ">d~y31Zb<KQ{|O`51UBkrkZ3O%0{N+-IS4O03VV8q@$c3Nx@@9#WV{BCME)G4TAvEh!hYg0g6Ncj%a`(sLCDS1+X"
    "1+l=lncA)rZsA!HHoCcQe4-Ff59VlQ72BUqfO0qmhYLJ1J7VahUzU<Id#?RJ1buIT0%0hl5XJg5l}IlP+H7KXv-r"
    "dG-WT8BF?Sofl%&!*5xAw?`3Kn7G>Qe2e6M}pxq=sD1V0Eh<CgP)C5$n)!3|GKH$ax4jY>3~y;)d64&vI6P~@hGa"
    "<yTs6ZEErLRXMs7Z7-EhY;8SrZ36S+e`tWrFS))AtaW+9Igvn8^YoH>vj#9rR<bpgRG#G4;l2Qa*1OR37kea4I0p"
    "&V@Bt4`LUpJ7&3P8s+u%e)7FqkLosHhZHh3?Y%CC-DU-KvVN@=WnXfd2|()Et0J;%nNhz)2w#5#UZj)lirk>5LJN"
    "6i4=C0|Q}f0)^QLtqpjfPEr6CrI5>=ZQd45>2(+Dl*tSe)eMzt^w1Uqd_8nH(osW6dA%Nxgrbu<#0Xm~4ZJJJY?T"
    "k{#O_OWNARRSStuyG7_+578><Fu1e7n7pBEiGrj`)|4pt!m#{q{^o<J@ZhSZlpmEs=SkB1Iui+!NeAIv&HEp8=Ck"
    "?LYpM;MYNjL;N<G9YB&L`G##3Hi=YiWlf#&_?g4HxC`$7MtM$R*UR(5w==SB|4pB5J?61Ne847L=BFSSX!dYcus|"
    "Xqp*^;l$tZQ`v}@>9o*f)gFC;v{*8WJ=@0|(KT95<tyEB($f@SKFmxCT3|`w5lqXUpfR<B86f|=l(1~+(bLcl{bZ"
    "=`2P=SRt`@sgz1zs68xB#%!5a5lQ!_L6_RK&W_84LyY0-&hi+`%31ZfW~0>`IOMS)ptRD#c4jS18BZL)Iznfsie+"
    "3<p#Jd~4wlq2hq-blw6yMY@Ei*;jYqtB0^fZ8Zl^Ds-|4?z#ZR!G=;23t&+Ra5sff{3|d42%|Ms)}UIj$}`%N_E|"
    "iz8(%$~RgBx8ji)?+O}Wdm(kUSBbt*s~z@c!SK&Qqx8CTwd5>d6<;-Ur2#aJW<%zs!fb{fn!n)_AX{hHZa^{vorF"
    "veO<pqj^(>I6t#2wG4aO;oBCYcZ)VQH2JtT~3t);w2~P$dkLRrA;Jp(Jp0<Cn^HyK<P@<mTDzXQL+MWQB0)+9OMG"
    "&e6~xG3QzN#$y+!FmoM+z?oLy)fd=*pZ>f5bQ?yN^AVjeJP#X*S3A#ij9!M`32ca!o6X$ak9xo{{4u$9BJ)7OFyP"
    "H)yvqC$AJX)nhq61uo3KWVGX(yvOJt#p(tS>CUVbcZ-?MKn^X^M>8ssx+WjtWsWmAABnlz@rDDMn6b6IJF4{2dG+"
    "gls8@%QC=sN|}n78_;1Bnj+}ClG%P<{`UM?xW4){yF9%*Ep%ZCez9<WbbU!5Z2t87#q8=6gnmAmmoLpJ{M_j9?D{"
    ";9uVxpVt)BP$!Y7xdJ<3b1l)qn5J>0V?eYw3FrJR3+At;wCb?<gNcNZ?;mA;g`?S_*HEU_wBo?K-zHe{b^KhZ)91"
    "M>#_-ANWqh$1AAZ;*A(z_q{^m8956S5;(qvVF41ZD<d;Q`7zAtn_|crR8C#w|sMZb>2I_d#^d$_KF9e6Wl`^H_zz"
    "p;iWe=CvSV@*Te|+^uj&%a~<_Q;8nL0yS=}6FO$0C9`(K(c$`V^r1(B>ySZ(MuYSA?pO-KB+drN^`#1|{WQ+g%*#"
    "ehM+dFcmivsL)q19QKUrnLnpJBeCm7h=X+h-E&n=48;GzJJq3Kl6BQ|0U_W|`r$wDF3dP4oTs0<1heozJh~TAp>c"
    "V6A>k30Kp6`mt&F**-4FYTiwyaJ~R)UQS`rr>A+*ycK*b1ntjkc$89BuQ55#eha5mo0Vo@+8MfT6x|F?e=Wb`xr3"
    "Jn?@o?>Ih>vx9~`|odh^rt{n1ZUHTW%l{rc#C9Z)fKH1zQrZ@3Jn&CEYLpH0upZ`0oj9jctRtBQxZU&FEfI=#9+N"
    "BiwB`ywS%c)d&o0m`&9$XNRRO0a2v3EA|rP}F<cX0U~LR>&RCBDrSxifO{QX_QO(nf{;aK=Ou{&3?n1rw~k9v4za"
    "x_s!J=)ZXOTi*P==K92+gN*;wAF6gzRc08l@8zXdebTYg6^N5Zo0EYfLf)M8GR7RL(bZOMh>uBl3MyH<}K_!v+{~"
    "C$EqH6`F;i_A`F|%VKPq>(HGhyogVQj*P5zaB*bDE$p<#OKkk^jJcXg*pjY4<Yv)pbf`KA#Rj&z-lbJ?^D$d&6AI"
    "D-Wje_h}=k3*9=uK0AB<>?&M-ELWRUezA@Ng}}7U(dNa<M#@r4+Uu1X3`#582vSI$kN}^xfVc}KOev`nzb9z4V$Y"
    "_7CF%z9kAFPB-8?O<?X<;8OZ%~hOXxbQcUfre!c`yx(v0VddV1Mz#?WL=KhJVG!$(-K8HpF*=oETOFPOq`z(}8x7"
    "EgbJF`oT4r2$PZX%;XoV%pq#GF=$+<q-C856aEA_jCNq!K<T}Eo~V3#bxt*DA&IJ?!NK9jM@4Vt9skM<Mea5{Cx^"
    "gd_m=@@evU2bXKQLX_qoRn|;K8P~(BoShLQr)%57ipWYt7Zp`rX<mbb;$A6t3{&Mv4@Xd?E8)kV<Vs<q}%UHbG`P"
    "uJN(zJ#BC&Ljwqg_~vvqdN77hwO5m*}Mxc5i8?Hw=|7d1<U#EcjlTZWOoYL#8xs{5V;x)A^LdaACOm4{qq$wAZo?"
    "T0LFr^bN(Gc4`Z^Gx)4=N$FEK|5(;tQtzmGX;0yzs~j+0Y+o)0J)d?JZ7}@aob=!iFFB>>X(jQ%Z>J!sSaPV&IcB"
    "ef&m_+C>(5OYVVVnwMfuoGE3qf)$X*@Y%h_moP<!<L{eO%gEx*kh-&X#PPtfA1k(V*a%P3>LfU`#3l{WJc=^w_~x"
    "xDA2)@`4i{#X0g3(`$`H@^G11e(5jeKx|V$Fn+aWo*Sio;T7$y<7K>t##kU5r*bnTm0alg>hrnZV(ju;vL0`n$}2"
    "{hR588UW<eXYSa+d#zf7|=56t{S-hTKowp*raB;&v^?hxE7+vkQ;R6jS>CyN@UE<l<>^FRG@w&!Ly#Mg--P_}n!<"
    "W;)93K3+1AOSuJ1W+A^y1*vtG`Y^ym@zg`10t*Nq6tjur&De<p<!!x6^lT|8hvBd$-?A^|v)M@QEBqi?Zer_{&5l"
    "58ZsN#_!m(iGJSv#Gg%g_oH|QkkbArmp`iI1A6(R!H?`8%TQ3Gyf6kp=Np>r9Wd$O<(GyfoI~h7wt~c2zkCZ**_5"
    "SgJF%3C#fJfC>vw>j_Va;MP20j_(}8eJgkFlzbRj<NKnC(dqq!4D(0RYJ4oFWM(IKA$cilx}@DMmz!K~EU*_0V{_"
    "N+A-q!fh|um#$rbf@(ce}6|S#eQmPR~|1)SN^H38t}sxz62Q&AAEwJ`}GFEXq#y)Uc(BhgRl*7O1+J2d%e=xrX1i"
    "6CpZ+X;}37ZOb(|9A6_1v+;D+6Jj?XI%H@po83Ksz{5HG%wJe<Dr&C&1F*Q?8POI|+>mys*{w}mOrO?{6i>WnMZ0"
    "kI>)jy|Qy#+G)-Ry6kpXF4f=Hc@93!uZ(D|EIaD`YnAT=K@l5o5vM3FDzJX<^qkyV;FShaB8hY3>8-Jk<ujGk9p#"
    "_59@%W@MCSa3Zj^qZVq9-iaT~4}3IGkWn|Qqd9edgn4cv%kxp^K1Yq)CO_4j$DB9rhCB@5;UoEwHMxI>p&oS9l+5"
    "HUx`B_^J~(b9V(|4J7jm`s+T(T_`i~E;sOIj~%_rV2Yp@PJJcNwG#!!<7%bT(X54>-t^=Pq<n;&}JVVc7Qr0G9<m"
    ">*gQV+X-nHGlpr&WMYim-Op&P+7J&S$`+s->&quEXUV=ey3?{aW2pui2;e~i~mc?=jQ(=C0J~`OyhM%m&w+$;ZDR"
    "r9G<P+im|};G-Q0bpi7tV{<F_L=4%W=YB4=YB-Ff7({=}u0@3(x7xq|2&87`MW;a>DJ2^c*eE;Fq$@IrpM{izE-="
    "7?RcyaRK_~6y_!^zRBqm#dGBLi(bZQ8`sT3?6dEb~<|u$ZI<`?pilZ~_qcOA5<;9?}5leuw;*)3_4Nf$^C`N5kc`"
    "3j*S=^!Q?KT7J^jo@rnF<#cvEAI?M9YtRsKDuC#)N}pz@ZO5Tt)2mPT`m|a49=8wJe7}xg#B}~C5P5A(elIWdx51"
    "OJdY{$wLN@HA+g$pu1;N-zOSTe^TiL@+&d^MG>ozu9;lZr*n5CQ7T{!@ZX;>KGp4lz;9!EnTv=-!gKEm{#gC$;)s"
    "b2PF)OBGLt{U@B!Zd>Dj$wCyEmxyfh@OuIZfP{D;2pn@S}QSXm-vw^_%Mn*x*3%owef0l_U)`}c;qH)Xy4ZFBsC<"
    ";Fxvj&f`J*F5vN*G!NFu5c3m62==O&&Kj*oD0fVQS9k9`(BL5p^V>%!MM<+iYy_vQlj_LasZ{Lx*d-IkqkOK+WY;"
    "#t4!ImeQh|Q|~YA;Nq(DL6%V-`VSvNV%*^<Bz8bhos>=S|cUa$8S{H_aN$I=cjcZj=<D2$Nt4%fVJOe<cG=p67oX"
    "_8iOgw-qbVEBP|K_m6-4jUtBagf4?ilqg(`qBBQaTj7`pOfxP#Rh)Em4#ZnaXWWgbl2?{_PD0b|g5D+V=+?e@`UL"
    "SFh;|=4oy`|yvPoMi;|6J8h54`Te#i1I`_?)vaa|`4J$mf-#aCqJ8I`0^K5FfFY4W`3f_h2{V3|$^aM>gdNbfRT%"
    "*A97&ZR6wQap0q<aB<;-a#A5TLkyJ-gN!DX}LOCUIhLcSzdsU$=zY@!InV_6B>^_YoP0d(dUh6EO`*->CMi<whXh"
    "@S9OpU<Ax66SM7{+z3c8^yV1Ai$*bQlXvDoI>ii&~nSa;yy}7-1OFaHjHr@URDWOz{%RKG|J=m97laxLTv3%g)Sy"
    "-Aa&s(-cAvz5l=<vaUYV@nNh#mhCOHOT%7Xj_@V4G@n#n&R;|JKVrAW{tgx_ejTs}^>-m|wTD{i3#^#&JKS;kx!)"
    "8LJ!T-<S8vFYnSHjh6&!h4c>Bd1IEt_f>xKt4zCu<3+Z|c)2k+SlVVIaq-Av?{F_mYrIob7(6Q~sau#SzB%d7MG!"
    "U6J+n&Dy)`blA^~korb}01j?8JVtax_6o#O|u>2PCb;THSI-Qcs%*7aL2dTocM{a)v#`%l)t#db_<XttP|@zajdi"
    "WG72*j}FUI@yw&d_MiS(L6NEwEXaEr02hvzxcfuO*HYW9bpqr**KgoU~or&|M5>RosXGc^R<%CA6fKw$e9^v2fr<"
    "chAtj7REv~Kq2W(1L&D-q$vwAOQ+*7tqfL@q1x6+4raB&DcFI?iYuF)&W>q)&x6n<#EEL(?Gj=1wH`LPg{`b;#hr"
    "T`=oZomft-a;qx2Au4YUhs9f?Jvj%l)LA&4n-F^sEWbY#i3=r4}of1aC?(*nbDM*HQfC@c8IYM~5%BG`f0N<bF+m"
    "?V*gPYp0)a7*Y-6%B9jd`D}A>RI{BWMR#>k32nN=R*7npmR?#}08&G-bmgWObTFtYDv=^M-6|7G<he)}jVrN)<h7"
    "C^0`W#KRg5*3j6Y4viAiI*ruz)>ial8Spo+rBQUw)7slFC%N@fzDYL|izO2-&7RWH@i(H&+^QdJrr(ZQ-+lftH5^"
    "dY89)c}hvRC&#L5t5^DRdh_^D?zh@p+>xwDM@c*$!1fVLsHdSP8WIj!i(00t~1t{O}d<bS;?x;OmogdG(}pSFgVP"
    "T(;x{Mvz6$KwU*Um47NGE3h~Go6_%gs)KQ6(L}eK14j&&WD>7RVipf-+nHJ5;h*zixxxp9(*alt3;<7A02}#8XnN"
    "&u&${}A=3X87laK?oaI1>)bT4bfUFkX5U@VKU{<``YnM%Pa;y6uU342x$UxHDikQCXKYb4*+3LbW-@$e!IdXgvLV"
    "-6fiITOz&3CChhByAI3!zQsrVCd}lP?55q3Kz~>6idWwO3*c*%Yk2d6&2Jp!B@s+$^L0ze^XAij^Kp=NxPq11>_k"
    "d(de$B7+En{`m?bwzZS0fxn=HJ~H0zWk|4xint=OouV$D`*cLr`mNjhW7%^58^IoL}3+e$n4@8r##pv&vCMJ6|;<"
    "+QU*sj1UJdfskCmF#@TwEYCm-ywi^;s-k-*U@YdF4KcXttT0UOUy#I=1rPQvxT~xvsUE#oxtbKYmPf<#}5rm8Y$y"
    "Or}NR!e^U}uGc$c^dO!A+U}Ni%Xg>b4EW+!Q$UrGepH=6uegL3cuGRI$rgiSKdiu_eTEM;BTBVGi(Q-XT{U+t}XI"
    "(N-x8q1#i7j#()jpf1c|?xhe|UFz{QmGI#VFRFYG$WzbuiogGHm&Ew;YsNvuSSs-%+0hGm_3XXOD&eT8v-3dP_Fp"
    "KIaFfGvJ1SLN6DpPY9s6Hrg9})&b+@6ZDL>5NB<msohSV_M$Uw<$v1gTAy+;Oi1j^9$}Dj`I+{pmI!4rx6Nkov@?"
    "BgKb+wAYcUyE^=*j#8KqK)^{y;MX)jp*?i)wf@cgZv`eQlx9lYcp|2DCr4PH&|<R>?~!;UsDJ;`m+BGH`M=!L4;V"
    "!FBi4}vSbvk54c)4x=9KWczFDz#0Q8z>QgVCc?6=IM?#U@8NAsRZ4*#N4_P*>6C5hpMtzl{Q<Q9$y}fUf+f4r(##"
    "?`^ajt^EkdM%ws7`*VSLabj#TW_0T4Qi3B6El9?OJ3{*h~ku0NPb`s1$b7o?c5(J46r=$AXRYWS88k(9iMJ(mv&D"
    ")dd5xFG7-G?u4sH|AmC-Y78shx&#I}KaaW@WOTNZ4q#=lc(z@PUpJ1(}ztiKdd-zS;@`E4(+URw$TBboCO|4x?LG"
    "MXX+EN7t3e=mdm^fx>&b%+WmMFvo+(_Iw{YLlwbg)}BYJwGB#0I(lhhjf~mKGMtiE*(>1$-Sbejw5EDhOH+qAg=g"
    "QuE~)+6rA<fY`Ujh%I)jAJu9f=`U{IPNtZYy5jF!qW>N1G8F<{C(TuntzpGx|*JqkL^VxsuaN6^xasBAb@csu_cp"
    "Psjej>nYJ8qUVx)2H$BPV!5XyGin%f1dqXRv5wxhJFwY7E5~C(6lAvC%iT4EW~IrbEBbk*(;gd%3zy*^fqhJqn3G"
    "!(d$M9Mt@!ydi+w3K7~s<ptWSO#0){CPCs9NUS^{=No{Dt)5!wL?7eJ`TQ`y7i_i#ccdq)rPLC=|wTm`Xi1)AG{`"
    "qiva`^sa`u5GMzc%y^uDOY9(F6SXv*BsrX*Y@uPW-{vWX&h*JBXs3ZtB?nh~i4Q0f<Q~<7FG0U3c?T-;+NY_TDmp"
    "eS7e=VlxjuOaFvj_a5p5Jb0V*8~9zeU%%ULE_eQq3cft*HnNzi+Zeo<>KzF_AD%UO%<2(cjH%PbE{OK-`0)7fr=#"
    "~L$E~Ekc>Csr&Ree=OaD#w!MiXygpQ6cQ!%^sih{lLt(wSgY+t)M{^)_UdkpN6P3MDU{|TGUJ?OQnwQ9PXy(rp-G"
    ")5K0Rjfs&#ImJp!7vER>CRZLWep{1<&1Ki4%6gjPt>U-=uR%9t1USwp3soc+$Q|NIo<cIZ3%Q~U(JkeRSll%H8Uq"
    "nkZEV@J3!Q(tr>2~{d1b;J<LD7e-Q1sfg>NhKHuK@??JHdXZ@+{%=Oi$LFu#AE#E&ROR6)X>%{WgxQK5Q2)j3?ex"
    "OI%c`_f_Ej?K8A2((Q(m!5UlF5S&$o~7PhT)a9-b%)uDd5AQ6mVsWZfBvBDl8Y{ve%lbT05J$16<6Z<XBuR@Z|v%"
    "+dgH7zXxxzkHU5jcPLLG*ouKXR8$_u8#f@AJqK*>8EI|ewc|w%r9qVSwiKhzppIIDIvVI@A5Xk1bh@MoJ4H%cS3N"
    "|7RJ`Hh^rAh<+r;D^8Zng{GN9IisB0#D^o438$dw6L$Uv8S^>|4_x5ZUA4rO3`H;-eu2~V|w`Y>zzIlq~Q^MhI^("
    "dv$fqna+HXWB~7bTw$cr@-Uwk@+EJx~)4;125e+md9|jH`?oGU?K&%l^S@6bk9|BF2g6qn2O1CJ*SOyXSjA!!LbC"
    "oIy@y9R9JE;;5_6b^j8lf4(;aZ5*YAAH&9AV7X#6Gy-;H?DxjZm*;zOvB3!!iS<`)w-X$xub5Sw)LuPsW4h;TnfW"
    "d=B8@+g_w0#R~A-@^6_`%$@Q@hmM5mj9wmzF-Ao&i{pKW~ym$=Eifr}~}R(ef3~hi_P#shvScGwSihY<}7tAa61N"
    "8$1N(H{S`DP`BIqR(pXUYSadoRt5vy(IxZ_M%!AtKW5ifj)oL|wA@gixBIke)WEfN+xh0IbWiCG!&%waT}2vt9cj"
    "orkcOTv-`}9cn{_|;1~*pF?B;#V!6Q!tR;+bszh0T-4&Ocv%bQB-SyP^&_su#Ar-fCVZdb4H3A*|klVbtK5C%F5Q"
    "Rrsg1b;?10kdeTqARC8=al{V2)$k|d=p<F9fG_}vH&gg6;@i9qC|C!(uzVcS}<pmCzogoiy_4#L>0cktEg06@_-2"
    "DNgo#5gWG!|{@dZ{<^-70g>DREDawKu*Mz1c-Am48kWP6MqN|lI9;unmNI6eO<?sshHWX`$C?uIO+RO~FPK2ALtI"
    "$d^SOlTC%@AE#v*w0+z%W`xx5ARXK2%gNoe$NEosVgCXBiin`3)N^A4#Czzxer(3jI!B9~}R5M0F`njz66IOr@v$"
    "-@HCNIX-%^^(fYEXoP<wH1eJ*zm?I!N@m#_RlfzOT+oG?XgI+CjQ*1n$;MyiFlCn?=@7?g&DxE+<G@`V)icUiD>o"
    "kMkL~OhE@?v9H}m3lLMelbBErY>85PTZAW+ex{wxrA`Q-tsmGY0h)d#%0o{uiV^}IE$qt3McG5BRSd_q}>O$yqtD"
    "=BDQeg5HLs-@d#k6aA~xB<wR@w?;0KfOBo>F1OCrfZq$nh;I<8Gg3M4C|$gZFS@8CwvAejN7~TRB+EWRoXwGXxoC"
    "!Z!$ZRgI^AgUNu$z_usM^%Q05|be3srr_|FyyAM7T{gku9i{c)dq@__3ZddzaT?mTtnp4ia7+??$WKu%ay0T*N6p"
    "%#J!EmYdlR0({WP`p(OcI^IPRX!RIN%JPEO<D27A;SVMF6JCb@2c_mI+g()y~ugRRy3Vpg9048vt<<dhCqGV)%#_"
    "neYr?DKMGoigSk+B!R)g1Y_DezK@W`Q-Oy{6s!m1Dq%8wwNYWF3`@XKTAK`nR-yvz^|{i8@P#hH72F!<WAIf_&0B"
    "9>4mD_5i-l~<7%U6PK!UKu+@imp1s4MpK%w`kS{_&}ghPQ34OK{FQfEBw08bVA6}-ga&}lYdGF{e$_ZyCt#To-_Y"
    "X_((nb1{2W)t8x#q6xWQb??Pf>1=CBFp%8RLUgIDnu;=Z2~n^O~kKKVP4Ut?~uD}XgZTL5CkkDk46~?QDihMArqF"
    "CYpY7cLZE$(=DCe@6>6=XV^El$K+_qp+JWxbO&*Y$2`Gn2SwJ#stuhvpdQ1YQvs4!{=SFBQfSw^7uDzRG(gnkrRb"
    "_Pr(iZr=k*)~CM1s`upaG?w&{{cGFsoVw3*4?Pr#CkR)gW5J1dEwWH57a|R9}P-_#ISM2Mf#(nbzp1fs8>ooN*R<"
    "C>TI>Bj6fTAq5|cN|-rls7%mk0QDSlHXd@KF>M|?W({e%@EVg-HG?`cOgmnI6)YaV^xzweYm<C|odG>aQMr`S6^l"
    "g!5s-pI1swNMWV}G?3X;`?Ksii{%o5@tYj8eeaTL}uCxJz*;AL18kOWg9Moxv4u%ysm5jg}^$kOxz%L>DViO;YU8"
    "cPZy1Vyk8d;yc>>1tpexW}4cO7UI1T|&%Lj8?^eD%v2vmNwA+FBOgx-EZ)e7~G54yVm2w|8e+&>T>`1*XfIccLy)"
    "1TK7)}-P!E7A5In(wSPK%b9lTc)i->tY*V4GFP1M|oTESN>v12xeuwu03{GDjy?=Lb^5W;|>!bJYn__@J9~{$ziw"
    "jqdPmca{@B;0=eT(n?LX|L}&Dz2y`U;}~dD38$<bG2QBBuz4;JKkHBycCH!g^Y|7n{n06q&&`pWQp0Ye#+MqtUyA"
    "_wSpFh~#K?IoevNV^ITO8?WkW46Fi`O)=0N1G?KwGu=g#=z@>4=>o4U?+@sb{is03*(~G-@ur@Hc3Z<M6pHFltdO"
    "V8bJKIy)A=7np6Cvl1@Ucp)avGH7pu<YOF5feH22JW0-n93%Qs+7z($t!CpMQ4xKXG=Qo#wZE2G+4|7V5r#k%CN("
    "e(wX@3IcXGNq}xSdE5M#^=|cW4XM^-Wq<^-b1vk1F=bIVGG{1s=a0ejt@V)KfG~L2%Wxf)dqU^VzsBuYEK)BHeGB"
    "`v^fvWU08c#dv|Sttkh*&?cCtZPIKswD&sv3ig){<o-lj)7b%*xGnD9V%IIo>v?iwaEO*^+H>ecV-fY?2t6lOxNl"
    "3Ey46vie<SR!1ab2#<2$uA`nXqk6bLoYf?a)4sI0zRE<Bq$!>ct&fV(57Bjm}xMx;Gj)j$3`P9N&J8Bfa?nq0RHz"
    "U<G3N9dkJ)tGnee?cRz@nPv5;4y7!R!CD-219<sk{IywbqmLkw7oR$(I!fj2Y}D_nFP!pi;H!ILXQ#aeT~__{&A_"
    "N#cbNPRhiM0Q$qv`O1D$*FkhfvV&0D?8UNt>=D&;433F|)oPH<mZbZCMWhcXs*uZ|D@<HOPM)`Fk=Ds#FpJ^hySL"
    "xYEp5y$0Qifk>r{a}~>2s`Nw=!OwH#UtYmbr16L9vYc^!Whm{#4u8A&te2CBA_c8(5-j_xFj`qN@iQQ)tm*H0uMz"
    "8A9#tudS}9(c9EY%9Q?uSyepD?C#l+I`qbV&)q%Bt>PXc+(PX`Dc<u1gzhk_<v}Ey?_{%rt^AE|#8_^NMdAG+(6-"
    ")ps&QI^EwF00>hb8;Z^L4XQokXm><LiOpO5A3BpMSXtUOt~*(Mf`xJm0s1h}*l{qnus(yPyyE+6y1IFX`vByBoUD"
    "2zG=A_d0yA;d1ak^<!_DfZN&3wjJ};uKc0r_`itp$Fo@kS)(g4A0amo4Rmjw^mpJKAHF|4IDYZ-^zhZuPe<GL!@m"
    "yt%JK55*&Am+2Uh^@69C=T=45dT!@s~yAN`Ciu8pOcIe7DO+$DbR>^awO-Vp4oF6^MM4K0jZy=Zv-V03r0<*qAs>"
    "$@7^++E^s-qI1n<>hI)oYFqh;<Dqen8D)WYs_|A#cV=lt){a&ZBls4^lbJK|H12>er_O7SKVw`0C~LtdoRy}HSF$"
    "gB_m2jv!;Xi+RKBVHaV!~vDSfH{oZe$EP6eMacW%4Qfj(e$d~<S?<`(ieBEBr4YziVmz_1!GXHdXL3j;~AJY!ppF"
    "W(xD@@-X!Y8~ufIz=Jp1yqhmpAWEjt>uBZ>jC#cRjqHFGIch3cG(-v}?`y4~oSP>u>$RC0y<t#G_itJ}%J5E7iYj"
    "HQ5~u;8)&QMEl$8=Ntx?GGB<xX*`>yU+2@l--~w+?WS6@b#i(EQQT@TH?7@m)@NSM8;DO<qlV9?XT9;!ouUl1Ae_"
    "xWfv(TnZeOTP<vHAAE4UgjW_58-bX)%Tau%=WR~ri2-B^UnhK=n_#UFC#4JP5YNqhON{uj`(hF)A1x~UwVFvN1!9"
    "P4cY*{y5-ROp)WMU}(BUcfR^+ubL)kkHk8k@ed4uHIH&bh=oDrRUyqJHf7*zx$EjMYWa1(8uU&__d6e!`pQ2@gO`"
    "wPyfO0X$KYDBW<{A#{LD=W}EDPbDza-YF86KZbAV-NT&@Eojm)?!O_VSbMlvi<2CAUAKU)x8v=2M&OD)l{afzn*e"
    "}QaD(LvnU<fuX{oeOWF2`51@r4;LUpj8LNhf`5<lxn-w|_Z&IemBh_VwGwCj9v7?TbHC5bR&)%Fy}j`ZBFt0ZI1;"
    "4K`GpsP02d)Yruo=xYP)+#}oG&ELe;)A{vhBJE3jjc2ZA(+ksGjM^lc-nqD|rqQedk1wJrYz;d}R}oPIi+b!}%s("
    "H17cUA@uYRc|?wh{#<H7sGS4VFSm)~2%@W2AVQ>XJ4BfA*k>U~SO)Np-9^7yBNqgPY9vZ)<V{}@Pqp^MT6yyC7)#"
    "U_}lX?Jba!HXA%?@kUNgi|6Ot1iJjwo5SM0md9h@R!_}p+0P~UT0<rNSlY3@s)pyq`BvR<Q1y>+VKA(nrb#^xywf"
    "ABxIs!$JNO!qLg%Mm`Cq(%|%!%MKsP9kxNNJYEQ>cvS3+f;WcM6^HkC!?fkcUZ{yZ1j=NjeCJ(-m@^OxvEfk0f@v"
    "Qau!53gY<vKhM6`iMY#ppLn`+UfLI{QZZ>95u3_0n*RzR)#`R1d33^BYL|a_>BzF0Mkk^|S*Yt?EX9GvyUs8nM`P"
    "?=t9id34at7em{2kW#t03Yd<ArDDJCrl7xH@nDye6<@^01FYkAO71*cv0`$YB=&Y7)4@RIn5r_RJl-3--4D*$#6*"
    "Vk?)J&vF+Cr}+0~~(#%4R$i>oaMrz_e^K+k83C%RS0m!}PG*ze7s8}^02h#yvF@YZZk$XA!Ju{xfCObvv0+cWn$Z"
    "qa>ZIg!hXgV6mz*SfS%*}*eS=JJLIHyoG$L5>LkVab0ydUbSi6U}aqGY_I~z3$I{JH5ghtv<RIjbl5U)EG?Tx`6k"
    "Jx4*Q4b^p4GVpdw*mSwQqgWJ~Ir-4Iv9_r(un3d-4x_SPq8{243zlcd-K^mKYAgoa)g`Bt%G5b^^!3Hap<0;d552"
    "H=2Ohm;3p7z`^=5^fC&xh<5ptqNFI_`5B&(CI8lMb48-0evhH+t}F0u&Whtm3IAt+lciz%2MwwT(I|UnLz(cZtq>"
    "(+S>CYV|@m??koU2IHU10r;np5c*)S{I7&DyPVDTz|SD@j^M_p({kBtY|)KvKasb5(cU<HTRLa=CW!y(=eD>_cUW"
    "{_r#=_T!8o0N9$(JR=pZDf?(f3~RvO#*iVg|i_k1o;WZS`8s>AJwDBH&dS2rxc<Nh!sUtq>14)2g3pkd>L2t$Gwb"
    "e}CJY85x$Wj?<NfZPfh*J#d*#UPgB8m#+S`3Pa0pZ<M3t79ogc}CJc8eB%P{pP-Qe_*w6<nk)GRpi>AlkU2($S~T"
    "BVb@L>-Tcly2vT#M;BW%lcINZbn<+_cpBJ&npO4<3ygfd8aqw!|$50R6yqvZjo-Pg&)8YQZ|9SZ0Lsv9lfOUTn<C"
    "ll;kA7-?eSLW`o42V#OFJ+f#t;YHTuXMkwTjdiG2I9Xd&S!aV7-$st|mhbMtED_o&Y?(V_@F~BzCR!d8FT_(bo3$"
    "5j`(*&ap}@Trs>v?Wu|)Z*Je^DMetS3`i%K2M+XxXDSbr1pK}?lCknH4jUglJ^xBL=LW#RkY;CJZiO-{M!OyEFXF"
    "h7!Gl$-vVbaUAATbwax;=OJ)Q3ligZwG+kF&$UFaqvwFnbF+BxGb(WwrNwY}I1HEs-LV4^CV_Gr1`yNI>6#lVMk8"
    "CSvS>bTc~N4-O(V<xW-{<`KS)z`bp<xn5rTaNp-?hNd7oxAw-`@C_c-8Y}S-y9D*`pw*D*XW}~c$PM1X;ZpzeqV^"
    "uR4`*+q%k>g;X_h}!BYeYPvUt{UNDnVvRp?)9;r&DiU>g#Uqz7lyA!?Li9Ub!;2D1Eet7*d${R882RZ76M`;hO+~"
    "%*ZKH-s@p^QFM(9TqI!^7olKJRp6bUqvB>#jV-I8j*tYRD%yyl7uBhi+)g^Ef+293H{9FE;g7>LuR@Dqs-+m>Pfl"
    "jl6n0Z_Dz%ONzK9l(0FDfaez-AFV@x4WD(hF??jB&mY+38$!1>c^hy+Ux9f^x#wxtCUQ1Gxn^pbt5w_G-6<yJVs?"
    "oiX#29M0KUD@aeE8w{m@1?+uPr{Z-Tx%0N#c>wh73;Svu1{1-5y*I3Xvc6Q^RPCP<bgtI~3~VIy2(x(2RYv^fPT8"
    "{w;zO7bj(V?lUlm9zWUm-rede}^C6%LPid-6!uE!1lxv!;iyneNxB$s4$ept_W0<lh-%86aVeb`+mJMgja%fT-0`"
    "0vfO6FvT=^94x;rNtxbWqIGum1RE*vuEc1PC&BnM4zYRI>mLg%Bd=wUSe0=bi&Fod);ZM4nmS}x|4fjo37ke4uw{"
    "hRdX1+SOtb8!58+-RO+{b-0RKM1B+%|=elT*5>secbo@kGtM;jcTJ@?&dK7U=nhFZ@=cZwHW@K=QrKep6hmYkR!3"
    "XWz!+ucqU*mhoynT6F{$AU@|;3!{HJ|JEevKGxo@WwkZimA5<Q4MyLNsnYmnqc83@`u0X8#K*Aux8a4m&Hk`gPa`"
    ";ae=GcembOpc{tf=tw!T~Zy;}T1MUOr<G<o*s?FrTJzh|la*L_C$BCr7~96s-~Yu0^r;24%!4lld5$gSMdH!QljD"
    "=S#){ihPnu0Ac|W}BwzL50@<uE}u>Xwq`KXeDR{zmm&kQ)U06iTX7gXPs3ah8&-mSGm=HJl_EX+;B0A`iA2lkKRx"
    "|%9@YiyAg{GL)b5=*nmq`0#S?hhcmoP4(_}4r2NZ`G3|fPsc&Lv_m}gsEY<Sk+YfKP8~<+(_q+1i>o)$l>*3H6Z8"
    "P#eHeXp-^ZSARUOWZ|^@o{ce{i}(KP^j%9W4erdK<~o5(#L|&ptI<y}R$-ZjxUfzBqc1$=VG6**#5jFMp2|_qhcg"
    "+{aX}ck?cjee~w!@Td0LrRlrF)`vZM%_Iywh4a~YqcJT<m|aeaW2&f9a+S&0kbRbPS(?Pp%$sVWgNZaDijag)iAl"
    "}4^ddWj-&ZNV*Ej!O-+Xg@^S$?&4=TdY<>q}~t5ZqjAhpremK+pM(mJ8JP56Uz2WP8o39iamGh;^k;AN7IIr7Z=K"
    "l;8_d{fn0HBZ_VMMs*Afi!RxYf(_BjAix-NW^ksrQ%xFP?A>8D4NjBvVVlR)X=P^@+O^6Yp(|$to=i;%-nx}$tn="
    "+xzX1LA5GeSU*$^SpmBFbU@*N8Jqoq|F8lt3N4N%*8N-X6Pl`a7oQOsE2(7|AM%YrOi(xPVDsWbGVvrRE8Sq{gE`"
    ";^5dgCqKQn~?}Gs~FL#>SGeNpzE?)?8+3nUg^{?j)55Fcx!D0M!!}5~zYI0O+Kn&Nra>u*P<O*WibjM<=%e^9PUY"
    "`7;MI;^^uEe3*dTYld2I=x%_*!UFLOsP6@Ay49?f%$ZUiFXkE&=<3rs&-OHK>3y&XfBx*jR`&Z{!Qbx+{(e{Rzuj"
    "HI6#KX;=UwfAO=TuOHgxa$>QhH!hw+wMq8vZX&fuVrO9dLl%ip2BVce7WGh2J+PkkASwGVEDP2V>ef=5lbhE4)5!"
    "x_8QN*M-?`bbHrR}_wD3P@~x0DgIf4&HA=VR1Vm-Ei}DdA+j>pp(=8>aM~Ax&g~-+P>p@-Y32Ww_PRUSBdZtpWPP"
    "Z3TMBC-{;e=Y|Z6mNlih?X_qa$2zK3GqvkePbu;EgTM~U}VYCP>w24p87bkpHN(U_tx1N@Hd&YQWcq4+J&E7{3Tj"
    "^3ix(jklmlc-FQO^WNgE6jbTt8l9t?TQw>FW<48zG?!Wm_rP8eLnR2MRB>r>h4^$IGjc`{`*WoMIr)hxZqa=jE*J"
    "?eoz_BL93jL(fNReDwLKHFD2a&N4qAEg50ECRe|evoB?|xD=tgT4|+g-I&@sH-52-qva}YD2L<6?|wdbe@GZ(j<("
    "Lqv|ZD-66H#~P~CNZqMxo$|FqAB@43%1I(U1i@R>^<E-?r=Y8j*n&H%$F=2!qq1<tOCgQ~ca1P43;(u50FLOH<%2"
    "Nvt^NLXc7Z4bwN510A++tQM^jp=(>@oRJ8wy(ltaOw57?mD6MsI_gr#|r-7Siv_ynm=M~KYb3Dzpmk%<94C?j|ri"
    "CzPP&i#M?NBM_h+4hfAEb8Qbg^gnre|Wp{ckE{50v)F~;$qB`$aA<l&_i?gdMOhHM%j=Bpl{uS3@GZ38@x+3wabj"
    "O&7AbfPVT)EM4>!X__mOP4d_=!+VYX?UIxV|fJT|lhaay}jdxNZZj!wNXvAbMlIn!ZmJbQY3AA~#wX-si*9?L$=i"
    "O-{D2K-8^>bZ}g~tBuj;8Z9&YTaL7thGm__#lig>kZ<&b|A2osA-~n#V8!l4cejn{{`ig;#-s#lBah-8lf@a%g$G"
    "zEHhaY#i;jEcxYSZGZ76L-rf8$gzG%N0-`&R2wjsRLvFta)=ig$F_}kSv>>69G(X>1O|KO6t-w2?k1oR?#1+9UkJ"
    "5#lC9(@-!8KA7p9YkLH5=!JD+F&@dRw|opVFs%3bOG9fNA~=g(}6j~L{NbxX{*(xaAS2<-m+2|3y}24zz(AlObN|"
    "__(V$9OVGZe_ECEJ`98{U@1chF_g$&)yHekGrM~Y<eczS(=iZh2zB}{CyE7NU$bXtGnww1b`SM`NYDv<jROs`zfd"
    "1I1u1x;(8`nnMwPo`Z_h7n_t}utuO6~dK^#RM#H*-3_KD!!6NJ~FsH>Y6peg{cPzv<DwXnGNTKbwWTrgeAjh{!uR"
    "Gs)#H+aeDu=ikZyZkroTm%i_CJnjz1t?Tg^EOTRnkIlos8R`GdqVG4deL|N#o@ISFxcR;jaLXJtsGy1Vj|aGK+-?"
    "M{>=$%i>&fo`+{8uw4gdkn=WF1B=4}Hu8iIvC9w6O?hgP<0mOCA*MSuE}QFnu=4KQ)E3r6bJ>voW|iigB*cxb;H3"
    "0Wk^6Au*}5T>%yjseS7X$t3P8-rs$85m39g|XQuiZwA`Ko^a|kI%LPs$F*z?ikgh0jY<a?EQE)i-1sccWZksQWry"
    "C)7lqr-<%vDyf~TuA|9ziJo+*?J=)a~Tss1ITdx+U9jEV4FoiE3vjXpf`gwBr`rX@O^t12q(VG|Tb5FL<|KsfuS?"
    "<I4M=w8Y>G0D%@oiGDp;%E34~eT-C=>?ll&mVehUm}{B}~Le(w4-f%?XBtn}BXOx%=fni@S`Qdyt!^4_+R;J30F0"
    "aN1wVeE90<r=uTVQIFreoxVIgIec+)fWNPd?!%jxhsTR6Krr%OM86vN-pj+oclh|1gI7l{+vkrD|Kr2aadQjuil;"
    "q%cW`vP{1oHp=Z7R}PPZ-(lMtt~%S@h+E^zrp{M1;6V;aojobka>06XV6n=fy{TjqMAt=^3<N_sBezN)Ht+bv3gP"
    "q&HRYAcKTiI!{s-`l@Ac_ve>6tZSHSy>?g!D*Hl3$7-}K{2X=H98?u%~^1tZFJUJ2(>D<R*I3Xk7M%839dXZQMkx"
    "`X@aMQWmn;TD!yceM2ktFO;d&b|Ji%f<~WXPUH7jb_?bA)dC>g?k&uM5DUufeWot*A=*W@mV*t&I1|-ot{NL|dS#"
    "$LaG$zRkTOzxwt1`24c%RHQ5Jsh;f&-~037o;{hNk%LRi+-UwJ=b;v_1&$wN){j6l6|36DPcbr#KY?H&6->OH$H+"
    "1P(Kad5)+3y)~#yk-e}KeAheS9{mD({cXu#j^BVX19q6WKT?-3$z4oANz9u(<|9|^N&BN_78{<YcTuZBVchhBPUq"
    "W;i)wUT<G>3SxAW<5Y4LWGJiDH_=)Pi%)}|0W{=l4&9y5faf|-x$1d~(F>#mFs?}uVow|v(F^7t*hFnD<<?=f3XK"
    "S)m(ldzq%d$ryLe^8z9!zN$lZ)xn^+U@wP4C!;<0seYpr>VYgzWATh51-DD|6T0Mn)lla0da6#fB63#V9@T*)w}2"
    "?Z)gKHl$m~huw$gStMtds-I{Q@ZG9!rn@p!Am^Na?#l=Atv%G_tCY?kZJm|3#X;iOhQoo6n+;Lw$`1(Or-0MfvUa"
    "ucVF^!Xgb@?_L1+|A<2TLEYbXTfZ_|fm`?$ge)zqyOsO5XhN>D@bI&!f}xlcRSyw6Ab<fh?+5{F)fMY4$7jIJj98"
    "K)agFp)_kn%`mLVkMBNwfAsDU=aY(%dii)=Gd5uGrRu9XiEoJxI0Hr9TTi;#r4x?z(uN3&MeDxE(~ETFE>j7yUx!"
    "`!zw^qiWq2hJ_?Hsd{lb;H)fD)*W{4lo=6`Eu)W0D=!e5t+y}$iWw_r@;zyH<_*1wI$Xj7cO{m)4L{`+qmN;<!|{"
    "R{<MalgguYYy3B@hHEmN-?Pt`jvM3@)ag2@xR(hY2lewaMJ4MBdO7SSft$=ZT;P7?O7|s*Yv#ceeSHh$2VGc?Onl"
    "O{EWNZ<=;&^&tV*cjQdxAY&1rbVz|jsJ#aGaHp?~Iy4hnMrd8U2P=wZPos1qQj<Wyw`}MR7@ws>oXY7VZMhgpJtH"
    "a{8D_Pff4_Y+r$J-_$9F^oRYHa$SbG7Guu4aPOIm#RXidFFNegzdW0!Jzrf>g>|NpzxyX&Z?GjE%%Op_z-Gg~*=o"
    "x!S#J_MdaLzvj6bI^qMuO>e$jmWWrip-_9C(mNP?Zf9z3MD%7-xkx*lr7b&>L*6ZJCA!}v8Pk40-@~=89qP)L8mM"
    "6#Y;~SiSAEH=A2-KV=WB;Qocv>#Gd8;28QZe%)fEq|+xBjL)GQ^vM;;DaWZALV76sj}N_y1A`OmI&?pePry3B)Bb"
    "*OxXPkmT{N9%auO#;s*33j%cs-Ue+G)ajX$jG3Rbs>Z1CK)t|q?9_ZP%VY*txwL#6nspmUmi$}_6!KdCBC<d%Zrh"
    ";`z~j%1EQ-c47}fv-EfSL)4HO&LgpTt)dt1AO;I|7r<PXAtg{kQh=d`ny%Cgzz?5f}D6bRLE-C$d_4po~tnNK#_T"
    "r~?@BRg%@xE{Q&&wu#`>p<<Y5cnnKESix&Fp%8PCH&>#~J+ewEE@o#q@K%lHZRV+*eSnzk#}JigNIEHorN9R``1G"
    "`L;y#x%mP*b7O+XZSkR-FD9w0#6u879V4k;vfzE!D|-`ssLC~4<ypG;cCa9{2YTuC7&?0KrfPhE{_60cb`*2!cUY"
    "gHFCDmp?hPEo=^XAIz8pXcKGvyPBUnpNi(cDr%G|fufXyLd>qRs4{isukZ1Rp6*$WOiW(~78yfkv3C<CkOU7NDsc"
    "06<T?!)<EwZDGy?&SQ}U7&{S1~vV7BBNLEFi2CD==y<&!w0Senw5oo9yvs|P1yTjdF(em`QgkB>jDf@b}z^-ZYc~"
    "m<v=Kb9x^t=x|^(UN)Sf{dj49>7LUH8@K;V9Nt$vYFqnlWDn4h^xO>;_^(#iB0+q-)4IqdND9Oa(mK4N_Cs9czIs"
    "AcB3DSyluT`RqGwOp6BvxiroN)zW&w+*kMMqMWI(Y4b$<%`=BUw?9Z7K??JSZONI5RHUfJYID`EaL{EX}ZJrN|Cq"
    "XYsdN#Y5_jb8Ab%`^%s@&&y~G^^%r1+jVOsQAs;~aOwV-Ufy0F!i}zHU%wqxNx_;$sh>b*b`2}==UJC#rWz}=i)9"
    "yIq|YvVJ2*LGe>*vY)n#^psp8<~l@0rnUkrz1FPUwZoP9$!nvD}n-->B{Vw%SLvzm(bnv|w{M|BF~>3o#863vWSK"
    "{;xc(Q=GGer&U%g+%R5W3`r3%XQE~#rv;g;mck!<JYgk^=v*rY!lcGFGcVB?OJPDhRoCBA3(GGbdLM5=b(xYe>go"
    "p{_pzL&6mHi^arT>gvmwgBzhR52}+9%<ys$&dL+$Y#C|TH&JU`1Xz=Z~UeHv4g^rh+kqs{rUsITs)vl_}q)5HS#-"
    "<*8^GO-U6SQkAQ%UvM2^z%KRyk;iiz$vk3<8JMLb|rmneUhgx_<a*j4gJ7J*5U(F{FpDc};AmO?~xQYq3!+A5Do3"
    "pZnlCY{~q*AjWibmdHpYsw2vi5I%rh@B);BhUZi1J&S}%qk{;_V2BwfgW<xtAOn5QV(i{^d;Ll|;n1}yC7B)EMOy"
    "|%m62s7JR`zz3DV1RXIaRe3KJd4Szu_5z`QmkPLS4869tk@Xc{f2IXQ;AOeonvyO}6lmYi$Gypy2HeA&YC80#f^e"
    "8oHk0e^yGt3+6q2BT_78LZ@lOJ!t8@HECGQSkF<jg*pLRHEp;OC_)k#(;~Ot1Od{!pr0p*8wU8Vl-q&vo@CJ<fS)"
    "B>8OIR+RB`gb`ex1hEef}+C-)DB1$EFlJJ8JGLkWqt)wYnM5Gir?q?bzxe*prsTA;7^Z>!_JW7q`L=#Iu6?0;hBm"
    "^EBF|G+zJ9=nfuLTBpfhNLGK3-)gO$vcAXcK%R0<IJ!vIxB@1!+k#Ah*5K!7vl8_Esjz;SUkoCaGf3X`D15mkm4y"
    "1DJ41DM`*zRNzoV?g>;{5Cd-=o@*$)J(r20&{;t>Ls#}tPQj_hctH9uq_7*a)7z_g|Koms*p(W5uX~kEa=H=-9M<"
    "-w0mZ9%^}1NH*R};m@7_(mKRtT?=BMMc$;YF!v%Bi{PODVw`%t&T<o&h$y1VSs!OQ%kQ|x1<zT}3Lp?f`hR~dO1E"
    "}IWDUFW>IOxAZz-1l<bH3enW;>-6|Tb;08^+)J=*O${P=n>V?bCC+2czB?+!<}2fNWQkM@w#>{sN;N&>1qDD_fgZ"
    "n&2MT!SxHy8a-gNFPpfU%Rzwd-vwI_B^mq!Fh6O#>XNcw4(N=2#A68avkwzCgC|vXM0D3rf50*ez-J!<Jbu~MTw_"
    "h(%7=tQ9=b4)!Rb9egVET5~7gbi*a%FA%zXG_9|8e~06AqH~ru;32HC67C9+Ym|Le4=4IR}@w^BbV8_Pw<kx;p?H"
    "^zx3zdK1|I!D_#-2~OG*xOP(Av6q{C1ryB+iq)XltW<R#^M=Ki&nRU^!>I@@hO1e1<rcbScLTTOBk5u3ZTW`G287"
    "$D;4frneOTZ}-dt}V{@tSHc)<MO_3AuYk!#NT4iq&dRx6SufPe$u3PFQ-_X_?HHQFi=#{`I9XF2d%Rvd$ds%Sup$"
    "Mmf6?%s8Ky$^@5Js?dC(1!2>XJU>3PL^ongGt`7l!(m|urPXwVHp8VjVDkcLIEfYLQS!g0N!Cl1BfOm0bn>xW|A_"
    "QxRu6=0Gtb$VloEJBrHZ_GCT+H6{rtdMU`BS(OBZNN+wA!GldG;;Hd$UWG>SPZ#QcN-#Cp3rU3C`0Ps~Z=un*!Gb"
    "m}mh@i|-&H%&$W{6NFSS(M#-HdR6E&{x%Y=*BK&>D}~LaSs+IkFi5Hj9eO%moVuAS*^~G3=!QNDc`&QZwtha*V+3"
    "8PKf|fnZcpc$|<g|LEdDu&JIVddqPipc(;C^V1qc8sBdjh86er!E7|#bABKuS=hQ<k0h=0X1xVmBS?RN+#7?yE3V"
    "fMP*9x?!lmK$3OZPLaYG^fy5^b|i))>Ux~&Gs_Pq^~G}P+1@{v1ey3E1Xi`#kQSN#<D(dM47sylu=n;B%>UgI8Ew"
    "cpSY_po|CbgX{gZJTuUsmQ`NODSe_qXy{lt#`=3aI3*ksoz#@=+fSB^!B<7d)=Xav9;aG;`vPDuzgthg&#H!i`_B"
    "JHt2x8d))NR5$e30x8><I5Cca1yuEPOeH)`@bT?igt*3u~Qt1sFc+b6a*`DQ63s46YKrNo{6s*94OzP=(i4JbNTm"
    "g|%rpDd649PV@`76lbk|}NjSil7>)C^c|NE~znaf}DcQlIpF9~kYn9W-E$9g6!rKx3D>KD@MF^Yn*1LK+uhsZGy!"
    "N;>Wdvr0rRgJF{Rm{?N58fh{JPeByb7)X;?#)H-o<f5RSS!<Y={8>l2x^LY8FFZ+96Ux2x!c!=3Rt~U4GWaj%CID"
    "${S(Hq=C}{MWn#`qk2CmLIVFW#<9EEyoxIh6_025$EF<k}mm{cQCnT4Yn3IGjZe3FT(EDT_Xrm+x;&z?i8`NV*7Y"
    ">*5Af&^xKrhzgN@F0cqOj5EsyR1DWnGu10$ucXtp982poE|*~$k`Sz!u&Uwr*CSX|7QAv)yGdG3{srG1~HQ+@wU)"
    "LyDSt~Xs;=b`YSGawj}d8U7^i3%sSKg{5H+^Z^6D5-Za9il5cDACd0J0pl22i1-dQa1AluJFVY~nZ@pRiZL1yRhr"
    "^+&(pwn6kIb_2^lIAonSBr-8Yg0Fb!&SD(mSE)&PA@`;25Sxn%?gJ@U^@?SR=t-FV)<m1DjKPmxqEpizAw`j@r^X"
    "Y$YNsHR<Yc%NV8BQ_hARft5EMjD;nyvUiUfEEZ4X_5oX)32DKOZCgNEL2*4s!<L;lSXYH1E_!W#;0~_R?+3rI-qh"
    "9}48u4EjH*vws(JO>a`x%4qu;ffvy$2MKhce#1o<mhSGIOAhjpk?#e#$<v_~sV8tn;u)_eF~2#DN+fF8<XZl}GcZ"
    "TaU}TFvcH)5oQs$FiRrmtnA$HtfR`qoB1@b|z$lViQ!Qph2VUSI{g0Fa&04%ETnJHZn{|L#<L&5uu;88^gWp24Y<"
    "TKMAU>48%IcF{c}7Xcm$&UQ%T!W?2YCkqC?g=n@0KR@Bmigbz%VL{k!kx6Ir+8Mu#_o-E2hG4&h^c(NdaqfvV<jd"
    "y}L#(+FDU;u^xmAqXJZq7wE*3f9Z6gs3Vi6b;p<+ZiS1AS@BHK2?nzzB)~0!2!KD%r-$0Z*iq;vr7dno&S6j4%sL"
    "0VU1E6^CA+I6QnJ800oY%>0L^6Cz}&A3_`h0yB>AAa(X|8xQaTtOMW&Fc3`yN>N4t^`YM`(*`&Xuu+%*HHVjvW^c"
    "^G{qbKpxd4PkMBvzJ-dPTyCx8GG+(Bc`I4<yX$#Me^MjuybJFJLt)N%!^=%RI+C$G>ES^4Y$o(yz4sJ}@W02az=q"
    "f$H(xC$6I0BNb`$Ug1X-{ji;-Uc#T!an~2qoI1(!i}ZT1(nTx0tMN^#Pq7ko>1g+>pa<AF_<zR6L_|FMX6m-+B&z"
    "vmLCOqTC`~7Y>#*fhBj6%uUneggemk{VoI$t+n%u_r3^b#3n>fDw-ioFLv~rd?@0DLQNmBhNAJ#mI(&P4cJgB}z="
    "A3B3Yx7KtNM$(#^|lEN_Ah~%x<8`7AFQ+Zy28SkFTuaK_(3T*o3&MeqdoGv5VLD#kPjkcYAs%Z8)%^?5x1PI@DF="
    "AO=Wfp1wLP{YCMY>qVL_6WC!Bq82*z)S<m(9l;Vv9A?Kl{?*TKkDIg18f+TQsH0%w1o-vKw|SW;!<Q8PSqyI{^Wd"
    "&J$QU9}xdr@Z`Y)JMaVD!HsKStMr>+T}J<Y$AP~~V>R{X=mP1kS*XD(BBWYK`o*uLxD__HzW<~pJn54T64pYc}Hw"
    "(v77>houxVLcxgeFo2dbn+Sd4}B-I2l?nck(>*VwxIEWPPFr&KQX$C0cbJ8N+O+BA!`5t#~oorQO~#(&l!I1UANb"
    "-j35F_7(v1l^g40TDT+zutTHi@m;oLVbwnoXm1I^i%;If$wm>%}b#e;A2xGJez+c?UL_mi#mj!oJ5TkUWkvpBZGY"
    "a$m=9pxJ>zwu!^Mzv?=@e1SLlL-8oMr*+q<BC(Dk_4F5;#gG7ATW|QJIMdIHCY{D7W4@QWATo2v}pIp-f?$&`=UH"
    "!x|$nC$-Te%FIaiLI9A3?6_7ms^p0VI<)^`hAo+4BoE43_3Aq%*3m?jhU4*JV(HmRYl^Z8C+Y>YZ$3YTiR+J%O-_"
    "BocF%S^13m8HNn5LxDA6tG^>Wr;*|Q^Qdc!27i;Ko?y$&d|U#u9Mb-iBgiShcN!MoQ7EzMODY=POH6GrUdma>8*#"
    "!b?}1RcS~a-^sZod$5+!{N3hYY=#Ah!{9>ymXFe8Wqu@3w3o>jKu0r(Y1K3{nwb6T{`qMffvwo@o%QOyP!hjhSKv"
    "u@fZOM#nX6**GDgf0D7QM@SubTnC<&S#F+ad!2|fA?6@DZBN#k4|C60+`y_bK`Jl8d@`$G+buORA^&}gcv^ElSZb"
    "*iBn=GhS9%%H=Si?c<qxC<Bk11m+I#9Eb1(FEkIhbeddUD^o?Zx%P*x(6K=#!q{Bb77>DJe}P$;87)BzXgO5Q2I^"
    "35g~c<v^sv0~s%VBZ8pggaf!q!UdbrB+G-|H;kg07qJO$g(gwK@{ED1ywcnYnE5TD0}d2uhrne}#w#MY(K1L8sK;"
    "nlEGXeLh6@dZDIlhtbihaqIpib(H?oO*dqk)w+M*hJDUdon53ATT)^oz6>G^R^y*nQcRC2!le&p);q#_?hrkh@Oo"
    "BOLI{_369MND`g<z5wao0y;7_EVEfv1A!7<`5Hqi&>UZWdc>b;Rp0iUvW0T`ey<IE_%Jp4yxzIu>5?0KkxH_wrgz"
    "A^|haj`yER^T6{W9|8uYZzG>?F8|&0QTLgl(PY#yHb{l&orrzU};LXX|Mn~;UIoE2DJxpZYwn!U|xVAHDx9Op+s?"
    "GJbP3M@F;;O{|EgL9Be-F3vKbI+~lg;(uEV8*yM%r}a=FQel6ex`09S)tm(Q^U~h^k>*jZL^YI$B(%{wxT8tTI^D"
    "2}D<`>cuQpdLP^AZSQ={4fXb+J8!AizkETP>b(*_!M1w!^zSMYyhkX+V4Z3tGbp2go5?9jN3?V_2@xYR%yCKulOP"
    "7Ei7FD6X?CEstf4Y!La30$^Ss}3HxV8>sMx(dL27C=0%D#9X^iwl=pa}o(rB)|^qNKVh$fL?iZcfzSYaS1Ye7po>"
    "%Rl38bJv=kAdgCuoC1x=Sf&)oCo<$xyhEB;FQV9Y7n{>(~dh9K$R;&zU#W?Gv<kVzxda$B;(Fy#TlW{Q~~`LLS#S"
    "|R!fS}%>n~C9x~7ag|`y5WFC!va*&b7h#~)jSCXR{mgd&N+k%E92^v$_L>2dul5Ck&j@m%bF(mo`FaqtatT0iM?U"
    "j7D7xNz(zgfm3@Kj^^raHauvV2z$yN}MVwf!hr^BR%w;K$#J^#qLjHhy|H#dHubnB#_;s{ciQqxmW>+jYG^4=h%1"
    "B^cCFWEh~fzs9!q&ih4y1qc{A`My4wf<9}!zUwCHHC<jQ`^D%*)DZ9-wEv*3S1SJ&U%IZf$dhA__PVQOs9=hRc<x"
    "fU!B>Ar8GCRu`#QUreg4*ub9-6|#RJYoxxP(RaloW(2FoBo(^dL?GU{Fn19UwMR7LNZ49(^s*+XZMG6`SY)#o%i5"
    "WPP!RCZ<+J=QH+4yfu@dX0oow%~g#HN|0gTW<@rP6|EKpPD!RRj8sg*EPPs1Niz&x`z8<61)Dc{pBpCivy6R)5|W"
    "kL7}^*`G8VVHS^s-PrLd&YKVqKdZYrhG3ig6gS>WCr|ZJ?;;eZMKQ2jk3!Ied5BX&n&ey1WFvYmnKLSyVw?($)iD"
    "6NnKTQnl`M4}Gc=qF&=qz918l=!hpx1I#2E?ru68Dz{T7wYnR5D&@$wkhA1d=jQ7Q}F%K1nX4)7(63L!Eoq4gCWI"
    "S0o!NpqL?2OJJ6P(qrN*p*&$ha2o`WM-UE8|KX-tCL1t?mf)D>DmkAbRUn506v48@usH~gF@k!}-bS9d4+<^wb7a"
    ";*(^#u0=fsehN}?>0C2$awF(j#_XDmmkh~_S%M}#ECF-p+R-v+HMfQ<%ePK1myIA`%V0VWC(DMmn2-X~!Uyd?O6Q"
    "A{vml7fFL1zeOp#hhf8D`tp@Tqj^M;`P?r-Opw>*vY<*we6o;)Yrd%E}Qe!nD5Lz`iHD5H|M+Mun~k^h}n@it~Eh"
    "t*HG<^zpl3b`nDsjZ$KA3au0HS7hC?Z_Igys-p80$1Yqc!W+|+_Ifv4|*h{0FAL;k!qQ@6I#ELEXheN?yS{He>Y|"
    "6oLI~fnhGVoB3FQw$IMEJ+k<J03GPtMLyk4A<!&~>K1)%V>5Kw+)xndfwtH2sUXG-90%k7nx(ZG<A`5wQUKb~7n;"
    "D!y;O;{l$o-PQb}TmaY34&Vs~y(tDj0AB)p3lF`Sh1o^zB@i!Rk}S!x%Use}`t*nTJrJPh^W2yJb-(V+cS?yS)w6"
    "*WzD=;#bp2?k_2vDw{^E#wJkh`S>>btr_y#Wq1C|y1(RpB0h(`y5l_vbuDXqQKBxFjx&oS^|Jq=k$ZVb~-YEYE$="
    "LDakn&erzs8cYQ<AObF6aM?w?e!~7o%7Lw>Q+`t(BB56c-AB;k(Hr2XN_*g2AzpjR=@`$DzuAn%t>F;uu+qI;s6C"
    "q5G_HmXOo5J7>@`V!+T~h3{wXAot%x5=4iE2fFKlZ=?b3+Com3@%ZxHB9q!3XDusoLWNW<w^fBmHKtb9YOM<~LPb"
    "%}61dW+sPl?_Vk+D#g3uyS1ar>Tocv)UUExB?!Xq$l<fOQn1iN&BwdR<9{M*n3&lVUUg&}ew64tYTVqySs-pok(a"
    "Xou}*gply6c~TLc=|jpYC?DeX2Lo%@*dAfvo>4tTbS6P@ig`F2L(Dc#1zLMPG>NQP^!JY`%jLrzP9!Q_vBX%IFb-"
    "U79+_h9=R`1Mn$~|{`0-<$HSFL#Fw`YLF3Vhxi!stDJ;qlIbXkeKedEk>C`6|D<>=kX+oSX2w{ZK(&qpWk-<`bQ0"
    "65iR_pIP%Ye#|wdRd9fBWHk)vkMttIw&wMkWd{MdnJftH5d<ue)R3x#przD4iL1`tRF^vZMMG+4XyD*czPV#3+J?"
    "RQ2&gh>O<Z6Mn>Qoyx3mt%d6|^dC--#pA=(pid*A&FgWnVE;DJn%p%GZPlOpx07GgK_otSpaU58^2ec!%yg)aCRd"
    "s(7a(POpg5_&z8+(Zwm8fy3bv@UbfKH9*TAM`%t;%C?lyFQxAdNIe5ot&?5!AJlB*tfbs&VhSy?(_aOTtUR04gxC"
    "H02n3mirPZNQK~oPF4k)GzKYBlu9eLkC_obBT7;7XYB(z7_*28_hj<MSsrP&E~g-@1*}RU>tLZNyrs}6)G!HUjx>"
    "f;ERx__4Tu6|aS8;b4pL(*rwEK76i|nZ@NI@7!JQNh8Y-j`4@u)mg-~p3YWU9~!(Qb1&tk9$;?lX5t^cwmbipt9{"
    "<0db+HBR|)vKP{(;7{^#=!sK^!1WMn-_mxu&oJy&yIX3sfWA2D=z9G-HIy)uHm)SkUkjs2CPe3y<P@CxwU>3j;D}"
    "AWw_ti>sJQ>rHjBIYliMJ8~s+BjNV-@3f5IU#ek@Ud7~NTOH9lAYLo9xZ9cB4{YqxPo7Q|mhW9IK{*+4d$;|NEwW"
    "Z6Ori^BR5rx*!)YBj+vmO*z5-bSJ8H}-7FxtLmGJ~v&Ian{K;x0>@o_F4~d)DpsD^HogU@+7&ZBY-J7-Y60k>DNt"
    "+)C#H2DWsDdQ5vDK^hukS&R`~PvI6MXP1NWG8&r%JSu4#EL?7l^pP<WMT$^HqjJPg;5kO1PE>;B;N?TA!)n8HgE*"
    "vrDRI~ilpQR^JBbLtsTZuir2wpyv;6AyGRqWrP8V!)ybsrYIj|SlhrryyOuV)aFF{@&Sx7EQ@3GuQMLCEjKG2g-D"
    ";7ZvY_Rv<5iRQ6yOoW1WA9z(|LvK0FY88kR)p|PXRf{9jmYt<#IXY}B+cvWSnXIjM7eWtmEhLX-%^+I7+RnNX)JH"
    "P*lnS3L<^3o`+PN<V`8pZ&t`k%;n|rb*YdH6lRDg&On+3OvzHAEi;0uvJYkPrqLN0Mk=<W2_B+$#sl`5u?x+*H0>"
    "2oA*wyw)v|;=BN4K0<To4+0XfpRE3CW!f&XhRm(Rl}oMeC441lh)TN;Cv(rKDbR>OfIx2O3XG_N>$D-n(wEU$Gn$"
    "3P@>4Rte;z2c?*aQpySDKvH77_2jsURHi7oWC|pw^E@-9slY8v1qHAoT1tacQp)HVR~%FzOK?lUplP^tB)AlF5{7"
    "tUy>={Qoj{qEj8j^m4K~3rESi(3qQN+bh7#^Ec4IayI%wixT*kyz80Rozaw(Fv!~9nmVFmL@amS5^N;~VapwtN-I"
    "Pu&^0n#=IqM-=ED8s$hQc0^osWKb9f{N@C+oZzsOAI<y<mi{_MeJ6T`9G&$TbqVj@8P^roacMW_Vr&v@aEf+HlsI"
    "xRwf{L3Og@FeN0Kbixu_~6|xv;y_fW6*$=v7<0c%#va7}?`1=;i_c79b3fa6s57Tx-HN~a-t}CL`J-L3~);{}j0j"
    "&0gtmdsaoqxrd3>RNC*P7pyGwNco(C;zZs_oTw**z13@@N<sFaZe8)jA6UnBRM`4HqX11}hIGwjWw?rA-CZoC-Av"
    "!+4$Q5!x>kRk~lOaiG_s!9(wN=+MOO!x@WVZo6%0=<MGPs_FEgJhQU!{^EX1#ikp61r<N+cahrF<J;@r@M((M+K1"
    "zM^|d~`z$CrUVcSLPV0L}btxdJp@@JSZid$}-hPn<ES*E6g9-rXch^4?OWVz+{AZzc{Y|;z(+YX_wNA%{}LEM?Pw"
    "T93__W~_XX%D`1pJR87d9haEOX~krVDr?r;Y(KW25}N~49$EoFu3=YJ7qzn6DBcuphS&}fenet7%#*VDu|@qQg5T"
    "N&ZlR+1AgzifdHkLFG?o(p2d_k5CowFC<4ewGb@A6KunPmG%EK_dBT+jra^20_`#G;$pd9*L#0QnX(uR<kqDT#*G"
    "o?%GX@=80d;~1IzVf{har&^6x>o}ECq8S8YKWnj06H>3YIOyG=P!GKAA+JQ8}i<A|?UZB$1OMoS_Y%a4{G6RZavD"
    "657WnE0aVgQwDWY%m+#V%Q(aIScZ9PgM+H&95EXdfDqiY$TAkRBB6wR6oN^{frCtd8p~)n36Z5lWM<IR&~}z{3oY"
    "U;5L7la3SpjvlGdQZivp;Pf#W+NK^`iYe1Bi?H_*9N_=icO6X4=nxZEXR&FL7kwlEW))v-}ln2L8=V{BT`N!_IZ="
    "l97?cMC4xzPQ@W^?{k`bR|vxY3#v4%G|*u{B&1(Ki!JnPq(7?2PLg_vFBeZYV9AX1{ty{Z~3d)VY_lH8!mV$LQBa"
    "9e9@rIHCpskmOT}O)doIYPpH6sy~X%t9je}6%)&nxdv;?cUcyIRe5=gG;f65xqkq(eyM`6gg$taJC;fF}DFTtbAk"
    "dQ<moMMG+8u&ku8H}w7I-QQdIpB(i|cX&LP|y-nMleho<TG_#UjaGM&dIf3&ws)k^1bJprCPuNfMwz1cu>cf_ly%"
    "bnm*oex)^`8H$(SJB=nnI+>_Uh-iS0d1{F<lz1I7z=(ufI36XymSou^RdU;UVu`Yjz!Mpvo&!o)safU(!}1s-fq0"
    ";dQJN^dOC`KLW$36Xg@wBzjv1<r(gcItQ<4>91fYdjhhg}cAxS9bl7)-BaT%Bd055Ts8E~CWjBbq}UHk$7hLTq#U"
    "BJI)w<yQi%RGE}1VY$F@b@ee>QLWhCvOlku4kvdLsa^8DABrtwuTpX_6h9@I+*XaiAld8_{Y)d`^!)pss3?Tpo%@"
    "Y(1smM6-T%w*i=GIZVe01g$6cSvv)1A1TniWyY^X^=B&GZIe7kiX954*W6Rg7xnZDoAur|V&#IKH2njPXZ!c$xeH"
    "-_Mfb`uvZePmQ=I-Tmpd_%x9gU0WC3<D{N+|{!S=)VT<R>wSU%FFqXNCOo4C9y7|B3Z+Yaajc=<Mt{%Sso4uBoPk"
    "21PmONA0p>8bqIP5&mKV&k5~|l;bKTCkTp5kakQMt|gj>8&GIEXm5D%DO!x(C~0I|VEjX(L1&r}66QV1JbKWPHW|"
    "355EgFCTruA9)WhQ#gRdmj%1R#ubqOtjGzdZqMal_x?V+U<Nt7}n64#bV&Ee0uQRv}g5V+h+FFZO?X61xbAYK(bQ"
    "8Hz@Wl=KeqM%SUYBHBlLAV+uF`lh6<tVhih6_~kF?oZ{Ep5`o2OU+SG7AS18verJZJ^n`%EBl-2#8glC#r;^BnB6"
    "x$MEkm_^3h_Nt+zJ1BL7iH%j?zebk1+ley86v1oV<7E{4yE2;I#GF0~<!ZD;Jls%$#KaZSc%tGZ<f(C>Jjf~_7vY"
    "UGW4Qz^0m&iFwjN+f**D5L{lAut{BtjrjLsJCkRvKO#7gPdHq#&Uh!cgD{61PtUiwRsStq2Rzt9Qpg9=)4<dVhjl"
    "aq|At&)*-PLN7die?IyC=<FC(1R})J=m^#B5AHw_3{VMEJu31vfqpu@bfA^0M;!m-<I(%KC+~lpR1a&G*2&Skk3S"
    "tvu=23@&2p|53it&hcswNfS!rRezn*p}XZuq=xxeynH^Op>`&Q$IG!KadJvo_6TJ(C~DUKz7wS3lv!n|c$9T~t<3"
    "g5yzn_iWg_itkHeU)u85PW`~ZdxrsiIy0?Vi%xT0S?<cGVFvQz3&(Ia2q@Gy#U1>y%nn7Fz>QdJ~lD*y%bhsK>~$"
    "Uq6>m_1W^y;>j2liCb0XHq^jzgtN(+o-5Ku8pPTbZot&M2I6Zj-pZt7$boS}=_-B|Qhau%B^(1yZ`yIz}xVS~Z=-"
    "Tpsr;37wN`I^OkuP9sy7}_zJGl>pXwkMGLcVT?@?zV-@$)4E>i{?x`wJ4paD>&p_TaedwY9MuPAl-LQ5sbfcgqoF"
    "B#${_l?74way`2$UL=#b%V||FXa;u^RT75;mH?wmE>4G=6T=R9V%Pkyo4V=)am1#rk9GX8zR1s$8`jtN5pu7tdwy"
    "$9^n6Jndz(SfO9hISW6TjKmIyg>hoYJ&WuwTrbqhi{(15bsYHk=5$}vmvElH4@nb9O8aiH<xYsCTsDeqjMp!{siK"
    "o$l{ZKM!P8xp0U#2C0)QUcX+V3EMzKrtt8K}IWUy)YQZokdW#P~(tEfP2RXERZ>;$|?-64%!|KbczmCG=nBK76Zj"
    "onkm!_W(xx?oVa%(P?9j4DtbIH4S$v*dWkxkB`vW<0VfzEE)%Z;G=d-zTb)R66O;%lq(EycMLeZ|85sb8c@dy8jA"
    "z_f$6GK34TO+mOm>btxJ)N_b%G|Xxg*qR&joiX2!;*~NpPM#^BG{xJ9398@XhA&P#yL{HO{Uhp5?-CzYT?JXU$VY"
    "?a+p&-Ln~8)n)Cd(*bTU<=H}>(-*gEf6=q888m76s<H!W1@rEDzPI<^=5lEZx4Z67e}MWZhwzhDtIe*voo!fIr(x"
    "Os+dF{t`O=+0^sXpUrZxy}uUaSxEb#E)$sm8^F8olR$S>ry?PSO{o*$i8LC>5%9u|uL?503D2lFfUb^c|BO9Q^pL"
    "wrxIxphB~U^l-02EV(xsH9REYW>UFVOklclr*K4jdyp=vT7V4I`4^6?(QG*c%ZTh@H$74=YD*#LOgBjDblZV)fW#"
    "v#?Jv3=s5)AGJx0#s`TJ@ckxf?pVz;`WU~~0hp{c8n6=YMcV4&Dh2&10v&1{(-n_CTJ6#7Ty)(*zlg$A45m`pO0#"
    "dMy+JkB`a$Usx23RViu4eXDW#_8*^&Ce2WjpDb<wSE0!@dfZ->eShHVx>MuKKN<eDs*7!1|<q`}ICkKc!1s1pHmM"
    "MBq%(AkS#d#W4LlVvgPq<~*8v#nwABcL1N4;b5_43p^PLt#Yw=#_@RoMntksaf!An#F7BwJz8T`bS!3O6gmS)&9w"
    "-cW*rO=lnKhFsA<H4NXdBO45)$VEL1Yi3!R(?nsJfCl~4(4O%g=M?5Nj4Yo!wLBmfyuY;kKX0mdObJL8BT641mm2"
    "Z-ZnNIV5DIit>!Op*j3Q%q4Sf)c?%QHyDibjnC=siHu0l9`mK^v2WVpm0<~<pTOS5RL~J7;HXC1ytk+gSK~3<Dmn"
    "3Hb^L1<;WnoaZm?ndP1XB=$Jt~w4ct7#H6SRGz%)3weV()3D}1T1>}NDxmE-%iiiy^hJ*q28TFDy>8udOF|NH)9w"
    "3qtV5&roO^)))x=2_Gj{pLt+yLWY{$1e+lw3P%b-<DU)CDOc@T!N`1-~E)^W|n*@^cY@KpUZg(9rO2uCl^2917K="
    "3;-9vRtxDgupIO|<)o#8(Fm^?UQx<&KV(*~C-(#<QeB42#0zzrxGN`Bl(i9+?vRzYH)H+A4t_*o@dj!;y-3$vnKl"
    "(ts4cGh2IWgkQ`%`b9Tt0vgXN;Fv5@HRP4B}gV#Pd-k2(xpl~<xdAOBi8fh7b^=#XFnZ*_W6nMhCnXw6FM`!}VWP"
    "uyy2kv_QW;~b=cyz;6#X?4&^tC0m&18MUYVL-J)#cXz}sQLX6W_EnfX-HrXM8>^FN42~hjhocCs|oq8z%uZzxHqb"
    "lJ%oNhr`dc#_#B|%gUWrY(PJ>|s~wUC)Ec?o(#m|j^Fgx#)4sq7!r`Qb!@>*QoKx9wP1=d3J2xp_E4aVcH`pqcU2"
    "_=U@S?+f7(hy^{m{ZAxFBq?H*yC;c<yco8*BY!RItp|;29G^a9(Fj5ygTaA-f!dM&l<#(3IV|0E|G5(gHMYw2_hE"
    "1!!;Ly^M;4{TKidp&~I*5V(aSAlJPT7^u@rVVS2iE26dJptB=<B6QYS0VPn$2`Ta1VRH5u+FtmCIcL!{%K^<ekrK"
    "#aXi37E&eCRhHU+Q|f^#a3plI3zYS^J+7*}{&M5r=&XyL4tDKJOSp%_R93QQPd-sFHOtBkddCg3Gzn6x^<y^u>ta"
    "Z?8Ujrnk~BwADJM1V@8Q?_+7BtZdpvQipUdsc!+AwkY3&mtc8z!z|LJYZ5Zb9inb5yM&044@zbX4kbA-cNw1Sb!Z"
    "M1wpj|6p~a6CH8jE@<{ea3j)0U>4N?qeZKsD*<DUAzWqLhV!I1iKcR^Ki%9sqD7D50p}GqDe`}CcEvnE`=f^*P{B"
    "YX0)jE0qrdnI!+yDLH<o)^N^!V)L?We(4|7Xj?kX@wv$Ib+yxNX)e_CaNRwobj5>K<0r97_I!+3gKX2JqWa)mtlv"
    "<zCPSm=_J!?ThK>X}jIJDFT0QL%oFcXe38hft6akY}31n_&On7y~e6uwdAgL^+A2qIZK!2<8AMLZ@t}=<e-y^C~X"
    "S;9#$%Esiu3m`}_mC*}@X3VvsG^a5)g(USYSw?5_UWU4<_Pt!?G11Eo5sPZe?M&a(MOcr%B%VxPP_J}vqf6*D$Qm"
    "lW4eZ>q#twXr5lEp#6udug@mBPtNz<Ax}^|3#P=-(DONqcL8zc=>%ds%O{G*A83==_}g4jYsw%`N8n0K=mCW$`jW"
    "6LbM&LD)^+cjx7?r1LqQTwz;aFlZP@~?nj1?`|#sR@$vq{9pw110xwFE4{QHqvV2gC7a`3-3<qUG;Gmc(2IdJSvB"
    "(qX>+GCY!3t@EX9<G@CGNQri3pD37NoF3EvdX#G)NHiXyIcFNKxWA{D+5(7XFIzB#h_q{{V8{Fr}=Epe3_UP8VsO"
    "viHn^jQ5(ttx&gHv>Y-Rz{iFlywloazFKcd$^{0Tm+&|Sm+}(O$m`@4;h@?BGaMwjkWdPjXk-|FRcJ4G_C`f`6c^"
    "lL&{qr&lrh*s#QlCIk_Z|agR<m2XD(%yl90it1V8eWXp>aR8ER@lf(Mp`WK<X^lcogQ0^X3ZF;WA18CZlep`^e(z"
    "EJXHjb*?CcqiO=H^C7D<x*H&lAwtV9vLJ;qsDFaY@rn#2V~*sbHUMPLt8*6MU^AMf&4e<#NZV)nq<IBfKtAgl!5d"
    "YE-|k%)hs3p?W?lp)@xymQRuP3I4FA#EMl~m*=S-pyidoeP3p1L{Y!K@-r5?e*!WZj#`jX@^>)-@Q@nZ=hZPt8H}"
    "DIX{x-YWLcVXfec2%FsSA8eb?f5FyNw>lnR9&K!`by=xy|7g`n+6%FLxYjwb`3%e>uA@!l$hJLqT+3H9o|FN@5kd"
    "=^kDz3OZ();0EDRAzrQ=DVawS;+rXHx#qqL<n^Rx&#HX|XdX5%xsQF7#OBKk_!{B;@$~rZ$s2r=ReaSCKYu8H`S|"
    "YW{rg&7_p4l|+&=s1=<SEUPd>bV_v^wXRmcABRpXe|UA2!LZUD_@hr4O@LX<FnUd=B?0fc*#(9H~fxzORUCk@}?8"
    "gb2+C)4V@g-hXA_UFcEwMtNa@vV6<3``hzg^2ObT{DdY_Ucrwn|tNGRrGK=8g;t`sl2H`PpyhK)n=d4cf+$@guW$"
    "CYOQS`!Kx@y4n%mWy%9{2z%|cG>Hu;s1S^^JDY%flHpU7JA6Y{Ahu{_HD%=ufBzXavlqAr&GCNe2L<-QfGBZ%cIw"
    "()53EC<UUV$)99Xio+kg=c_r4XE0jfU|IWtXDpNedFufFcCN3wkVS+)QTH2A*;h4y3g*zHIt3sk6ft1$7x|%mI`u"
    "@d|E|wH3)okh%hj33m*_W?{K91QS=mtpm0wXxOY#t%J-ZPH-=&g|`$92Bg6x2U=5)_VvzXv~jUIN5(=FR$Gw1|B;"
    "3FmWB02UuVDL8UBTvUM{m6zq?`_j#%_k3pcmd0I6M2sN1h!XV*QCrd8??hWq?0s*K-2X*Qa$AAB7qK2U1d4wY$b{"
    "iuWSqk4MuRcV1D2OAaG=+vzYGVV~l-KAw;QnvB~vj?R=;C<iRTTZT9VJdxyD&z%d$YmP5ywi=Ea;*|9JBwp`oz?P"
    "j+_6$`E3(%^`sC76ZHLRcUmc#Z>{u>L1G|V)=p27PI(>WC^ohd{r-vU;e)({|T%@*d4ntzj=1r%mEIub6k1HSlv*"
    "V9Pr_d?zeCX4=^U3$nDc(+&S&%=9`mKA>q7r%!W1_0~`N<IsjI*Pkk0<Yr{ysVTe?J|aLh(O*IEP|?_}|BGIzy5z"
    "LsmAH8w>hu@}*3=gDP}`YF<?D?G-fi?BcgHOz~CpDc-8+?M|t8^I$*J{x(Yc%WQ@xgzdeGaPFllo77oghI14Q78p"
    "of*X<mQ>dCDhWSu7&h_`fcQ7?A0t8j5U$I|w^OXleUs!+}*%M-9CoS%MrbN&g>Ae%@_le14BKYlocw}O3iFso18#"
    "b;FWUoHU}zE(y_X}JkJ-%{*vGkxq?{BN@tu^I+87x;O>!RFdN94u^n_KScApau>?J1a~E%d$_Ba}1eJ7!X2cSxT-"
    "zlUoyr=h;dVL6e)ng5fBp(Qeuc1zKM)jr+R*0htAi7^Ff5Ss!es&hr?hGYp`C^S}~Ff9fJ3fk+q7dOHB15I~JgOp"
    "NGOO9fFt7E)x%qE?Op+@PI&q|{oOBjwrxurN*GRtC4F3Cs{wW~r?V4jMDr9F)^ia|@)PSR&AX(Lp`o3okU)Xzi^8"
    "a00MX!dq}@;Q8JI7dft=dWuS|0+JGg8^xTw(ZMLVUU(5DGE&3<MNYz<tlOV!ZhO#&lOc%g>1^IbWqwkll1JWIZYT"
    "KfUY)#u^WpuQcc0EqemQ=%1}4f<fe*c`owuMUzq#wF!y;5Qufo=VB>W9$S!lECh$ml_tMOgJ*KDua?-<c$9elK2a"
    "9xs|?&`6L=@;l)vz*5~vvsQ8`_yz(=$oE1X>VCN?r+&$x_>qo%zTsA6c#C;ZpvO=1)TTZ4zHKN@#=?BJhujx>X3e"
    ";2AMR%<w*c%od(+wGiUkPN(;S90p}@+doA*ys+u%W&7d`#U}k?mIsfUyCp1(8oOx3$TqgMLe)#b2<iiB8<>yHo{p"
    "^?H(=+T-v#&SP%jv(Wx#x45;R1lGG%(Ha`G?6b00SRR+dH4VIeK>le?30=@u%~%?&s;cQzY=K?~f-nBz^zu5)x{E"
    "G@43Rpd1E%Tt59tW>%qI*OlAArH6G_?ng1I7p#fDjVPUVsKf(u;vRAcER64!vqXy`Zj13X`TYwT0xhe1<ufyHNf1"
    "PAmAkp+w($(R4%ysgYTild?TzqV6=MmHY~Vpv+@wnnJ)}w*@zvFW0B7)0-YMWjo!YwcBq$xL%*_7(R-=91vRs*=t"
    "D}^v#=oWhWWGI;y?*t3ntuL*?Oc2#Mrlch#KyKHwyoyFJtNyzn|!O8ZHpp5FKFAMz7I!jn;-r%+zkLdtoGDvG}6K"
    "R&52MYS@H~?XuU~{i<GoY#A(Bw&cG?$(L}Q~j8-YZFl!px@3=r?RE7j6ebU(o1-u8?#W9XkaFhdzd2OQ)oT->;2w"
    "W*7Kd#Y02TFm~PM&5-Lez#4%tru3=#`_v6VE)x8|6_EVK71|<M1aSK~eHh>tqaOF(5$-$-R&mQHnC4Hj@+j8xWR-"
    "p&8wljSOgDq!|y?6GbUn6LDspiALo}pr#xEmGex!j{@UJ0fbuoYf{oV#*9@mNdUg!17S%SXCD*WO2#XgFv}j?MM8"
    "_s^dFvE%X53-u=a%<ZW9M+6?*kt3ztN%=$NZ{Snmf*x$7?JpLeX{*5Q1%fUhb#{G{IWMG*pn1SO}-H=|5e_v5d@l"
    "2)N%;}yI+f#D6?yVQP+cyawkCY@$_b_BL<XrLjAErR`07JJ(Lg@5C~{$qN1ds);d%y+ZPA~DOH*LW(F@jtyPmz9?"
    "r>VT8*K%6>zB9?VmRzZ+T_VRL1cqio<po3v8*oc8`c<M?$*Yf+-cY;_ozGO7hl`nsHm~x<s&RTL1%oBF-Im%EB?a"
    ";Cs^qIGyGfsa#c@MO5@@7&KA^^+}C;yln|KrV1NAG_;p8P@wSlB(WE_L_Sbbe6=Y8_ID^}mC@3M2);7#6v^U{kqQ"
    "vE+3XC3<?9P~TUM5#{9!1^HdDatX?{eA!!AoBQv~kKN`>2lYe0@5;}uTiGju!Yp^{9$eYIi?8ilgZHHv6=DN*E}I"
    "+cSuLgvgB$}URC}Q9zUSm4aNNzT-Ha$1X`ug4eX0-bE|Nn?!yZuej$$$gGyOEc$G2DgO{&$539VlI{U?{{a(3OM;"
    "PBsWN)ACPv@l#@rojTEU0@C<+-)&b826YFlVbXhg$)M$un((UhmN>9;iQ1R@+H{Td@>%stqN;{57wo|anx(;%DS="
    "Z+YQd%&avE;c-aYFYep$sF?9>d_EWqm%#=mkRE-Nmxyq2ZY(O_Nl+;R7+`Ha^jOiZ8_yJ;h-DjWqZmj&=VtL)Y1)"
    "heU$5Fgqgz2QlfL(x}1_NnXJXMs*Ynln+DRPrS_J&YmO`=j5g9%KO3P7bnz;)>C4&3Zr1|XJ3dgrs^-UOB@p+-1E"
    "fO@0goF@%8WI(B!>WD|G=#yiaMu1hCSemTQiMl{!WL`-NB#zOFZLlg(4X_^>Ciixf5XuebCS#B+V0lwgn4r<4O~K"
    "jBOwgFJMF|hnEfgwQnK_MwqMMFmLBp$q$4QPBm_E`NO86@;GqAqSRx+13*TfsjxFwWElYzCR2$6UZGH^6JMTmrvi"
    "-|HU2P+-lK1KKznA}A*Y+_t?(;ddh;zkUvs-uv6g`0)q($*#)Z(|cTsd&-8dooBu4&Am*L;h+FqdzzJ-ioXDjn8e"
    "KlQsMdZ+Lc9d?UUGopi7ajS)>t$fe$w^V<yb>l7V)+7LJM5@F7&!*<Qaq-E)_TKo@i-8kr8*k%sj7h?CDVI^aC3J"
    "0AanuVq$x<_p6(xKHm{JrJr%eSvH_+}2gTNM3zI-gw+4n+5J3fe2p!e+tUaU3OP<*(dsqCFo1@5JTim{@BdcqiU|"
    "%uS^~F?A0@1uF4ZWpVf&v@oU}1*u&<b|ZGT>^qEk_SYlrUPhVmj8_pTyf2u|zAZ9x-vGDE;GQb=GNkrmV?Qke3Xr"
    "@#%xzw0ca+;iUxT9L3*@<h1Ok1$n#IK~EIx`F*A&0EF5xOZVXW!WSfJ@2n4hQ$6oa4PFr6%%F%JXB%_`s3aC==qy"
    "-LpfWj4RriJP~l;3_566)wn)ip1O%ouP24#w?dNg>&`|{2#yQY{y1keq?u8UcRI}93L+~2G|OTmlgHdQt+~RJ_`6"
    "QdGL#1U5~M!jrN%9-6b#4qLl)-0tgV2FwO)M+z|~R%1!Vt7*Au&mRW;lyvVvv%Vcbl-V;fgXUS*@mkB9hvWkkJx1"
    "bfCFiQjt7JhGlRRbU_;A7zUa%0xiav~HHG84@Mjao~lT;y<HXazioR_G!qmGUx139O4a46UL?6{k5wxLbyY*py8S"
    "@K`9fQ^eS4gk%;lJ2>Sj+9?|n725l9xR-?c>WrcGvW4;zVgoce0f3Jo8ng)p#s=JHP6|bU|0$(VQE!#>R2z)z9T-"
    "WHq6SbI19$r<;RYF)+ya4nnmzZ_C;?myNbHO>co|pDGMPPr?+Df0>0}<@)OoOCZtH;9VBqaM<=cxgSq{DS_Ldj34"
    "RiM0t9pMQnBnNWH3`E-=IBQNh_mxHnds@!`?nu{ZrpSpCd%|kgnhmMkg8W0*TbnLUW|7*&F*nsv+#nxgoY^9|M2n"
    "r<mZ$BK0ckGG2y4PwjGLR(f6O;{&<W|D~r;y`edNzE2V-92X2^jmwd$;9KNsD_7Xp$T(Fm&f}(*Amqxx@jZYogw7"
    "sPtJa6UkW_j2O3R-s0d%^!g%~oT7*XNP@tHYQbSie4IuY5J11osz(z#U0H&u*`uIq3IyayFBG+pU%|{&pK*j2%{k"
    "v5q?4irG5JQ5))SwDDDMnC)x(>)+cm`ASY*0kSLb6rJ2L9ob+$Ehk{}|L+#PfngA0+BEFOlvkj;1H3~2{ItZDcyX"
    "vK!Puvcp3=)wfCrCd7Zi1NnT)TY6tyo)9Y=qRjW^SZP0^gV4iQuy2cz~fA*Nxc#6edauZO69^!Aq{m>4GKA3B5T9"
    "<QH%_yiv`NAvwK<JHJ%(y?|fp9>RQSGjJ>9fyA%U8Oz#o!;~vIoEALm7S;d%4!2>wEtA;mD_ru@2GFs-JqjkHj>^"
    "2-PvpZD$X_TLv>dz-|cDvoD8pqYT$!QJl*B>DXCB3Crh5*3<)d)mUPq2n(OhFYyhyz-V0#+Q{|%&Z2y6~B5e2Dm%"
    "y;Y(mp1{woiT$6l*eN#sG0iPCR#jek^&)sU#v&5diWSbuMZJcu1m@A%rNP&?;$wOpB>xGX?N<Hf!eqiM5s1W-c*d"
    "k_%ZF0R&75@k|PUHyJRJjtLalG7;u^M4_340)$gOx&W0mQ3QtU=ztlcbb`Vc*`|=BkU-B=0Sfa(Fe*9#wJ9tO<On"
    "1!3_J@!S~CsJCDCd+iVQ?*0-!Y`%1I`TRTKbMD8qrcgJ4-RyoHs4W<rxmj#%xJ_Kao>1Zjj|E-9BW;S_Z;aYbon9"
    "B^5A>s5dkM0SXQh~Lz~0b0p;^21uMo5`D__wPR-+#MhPcUez9y#Eon=IjLfSf6Jm?~cAdem6P$_2-|D&reU@w2=+"
    "YCIEl%|H+5%&yG)j0ohqU5FU4o8_Vd7^~2H0yH6Nu;S=2T==9A`z+aQ2v&r%MAK@0qr?~mtbgX8zt_JEKC5&At6E"
    "?0DV}F=sWSlTZ;>EN|V)|F$<E>z~0-X7`%gVTH+>m?W%EmYEuv5D`_|h&gV-Mqc-z|B_b_TA)o8FHzx2x$&_^cG("
    "HGGfS9-yoW177jxRguH3-&Jqnyq%}#2cO;8_>-M8*D}28ggby|Z$D!xgFf}f%37?P`8hOgoi^y=rsTG(q|VJGgNV"
    "UcG1!q8CXroY67}e?z{_C|Ub^0ep!S<vl|%a(p<%D_asDWOE9L^}y13t9mu(|_f$W~%zyy-JwQ90#B^yTmYMY`%#"
    "BMRF01)U9!yPp({mXz6+e)K^JUTr&tF9c`ZugG|S9zb-vlUP*ObgeO4HnR?LWF)WaRW2p(Nwo!?s+{cav5$myZQ`"
    "IYNp*u&-`nlkV~Fi?(^NN4?p}+8ldm*Up&H3emHqk&4s7OKR}E0bV$Fr&Ew~zhYs=0?2c~>Q_aJH+rkd%R>(Fg;I"
    "oCbQSBZD(}vG{5r8JCQ8M{tNc1sTtGuJxU<^^f6eVdQkqGSwh6<H31&SuNP%xsQ(6*$;rQCC(Is8Rt$rAH~XiQnF"
    "8F9`=A>p<L$V~7IHFYkDq%*~TTWWkkBLUQvJeQedPXLgT2CT~5C&fh8(sH<+2eP9Eo=%kr&ZrPDW~yTh7_iV4v=l"
    "T`h*m1ENf44cB>?R>)Cou{CB~?7(TT`KqQr8oc}x;GE^_bS7DhuWq^LRIA}7J4W2<z5L5(aL{{~I0#UQMd=qv?=y"
    "9&nx!&s-7Vr%;|!glh);WC-V@+!^%exSR+3;f~a6rkZpV6nHqRwhgzk4{dPeEb&X>#`X*{t8Mmd`RjHE~?3~{d&c"
    "oaCc4_zT95@b27)3=W7Xbk-lQyRyDW=RytS+D!p47@07>(%sbXz+-_aJ`c6nPymuwFs`VTm3lno4pbxPW2H0CP{y"
    "IN_Dg1|%v!4K3e+Aijwlo$<X|&#ou`b!{cG%fp;`@<{@YPgFv)=sl>HUA5O+Nep>&WraQo$m0eDw3=BNQD!#s#R%"
    "m!l)$l?T8Nfw_A>xvkY=flu7U-j4nE?w*XV2vch{<v4j?K&3No1KHHyJ%1`#zK`GY7F>)wT9vI^?>uUgsp>Yoy?2"
    "(rlXo<NbnAq6@ok_q`?7ZMcFQDvSq^Gu*VWmsyP9l`KyAbn92otGDLoqBCwLEq*q;r#m+AX${i|2+^lT#V$KGw~8"
    "F;r9?w#T;GxzSVt>ihedjpk+9aOG$2;KnnBfrtsuy}8rKb$do0A25apZ^5^oxFK>bapnWl>9$V&VPk*b^hk3Zgac"
    "ZP4B9_mn{SwJ+te}$u)MTOB~uav)SbL<o-EvRm9*jtHIB!(z}b^%+=o)T)U}ICYiRc^|}>hrpH5F&+E=kSN)DPei"
    "M~hcGIJtc8{W72;9(Oyf?47&ltB0W1rQV3-e;hymqBnx*70l?|TmQ_DAXjOLx}r{qe6Kpzqb^4bUd<&(I431Z8_9"
    "^QtkxUM0S9SaE{Kad+9@(7W$%Y&Wkz+@{BN+x1)RgltolXS+SJO*=fwp2-#k>20LE{%e}4zy6P9!?W{6$LML6Vd!"
    "e^Y_i;DLzI`)t0>_4+!&X*Cfa8!MYJTsp97i#m;hIoG?heaj0opt#%(1gv(pJH#iAj>heSirOn8nN;+cjgdINQ%6"
    "f0?qaXqt&DxMW}N=mA2pq^p^c$Fz9gh=#jr=Bqhg>szXwp(;G!Hh4npb_mWbTUpvc#h6e5>B$#PK%TkBZhNsYz)b"
    "8B@NLM^S3kSnL@LOAPw9bE8?6W7MfeT5Hj<cNvJzho=Z)Wq`@(a4+o!9li(kl;7>AgnFJx6XTBdtgXdr<@~n0M|I"
    "Ax>54Y>~*V<s)bwBLEHoUg>L?~Mphox(7+VrXfKTZv0>-zwq3v)!mC22F<?<oqwR+Zf{CV~6<wRozo^iAkV(L$J8"
    "+lbUOj+oT9ec#(|)fQs;uds!+Q=EcrcAS>(Xw}{Q8Ey$b<c8NC_pO#Y)<5-*)qbL)54`59>`s@r^PA?71t#`>vZ;"
    "2yFG%cDE&<A}zAYLmJn&x9!fdf>yQitgc$Tc^iK4f9XL}{|(9ld}$-sTot(bcok!+fI9(Q|XXUF#S#eY#-Dv!L2u"
    "(k*<0;{!v$H|g13ILS|YJuPo!jiTMc*`nlspH;iC>sUlO2%tV5)_$J%Tn>`GoA<!Sge_q$k&2q2Z+aW@F@t#0#EQ"
    "0N~O~ZQ%#8!SO`4Y%-|xtg%`kuj8kf|GAv0<Wy>vGPniHL4mKEtS*L^s^s`z*Q*jrZ5Y%W>qQn8hI>NK%o;ge5b_"
    "@s|KohQocGg@ID1`vzwLrp7N(p!zOo~bh<pV>kHXHz+M;f&D3Mvn6Pg7(*3K^}ESt%hB@!kLp3vL;SK)7fHlLS0Q"
    "(5-2-w=>^hLor`32~&=6YrcAsXyE_%qm%OqyxYn9<G&9NLEtaP`18q|5AR_Ld~^PSX$n(Lg>QYa+%AN0qqREV?u2"
    "xe{<t~pAL<`Auk8?no%}Pcp`u2*Z6c!K0q2%9vrWM^Sh%;fM~tbWv({cJ#Xvokv&ynux3faA5gpluf&i^wLKALhE"
    "5f;diYas!Tp=Xt6>2TL{3~70N|>iV3CHYi5x=ZAE`^sq-!HIy>ubG7qF?V=4P76^2fT=@VsKO@i1sxcHnZq=n+8l"
    "RwZ8*`zn=Y8Ug{osWgm9)>m!4`{{RcYo8ynzx!=G#Q2P0+XN5OCYN^4&{f;iV;|U01r%acVu|-YwtJaWbc9pAm(b"
    "MX~{>%ci*5D+)p^w)8yW@|AL{tmAHY<Q*^-*%YO1~YSpZ9nAMrX<Qb}Zg%8hBi?xSIw078Q9>jPVqf?wiZ8>GX0m"
    "r|wj&JxssP7=bd8(z(POK#I#UGMar3%u%161YBS_IB8|F1lYqcDU}yO2F|Pn1c}&M#wZW)5v0L5)+rc=F|MV6Z#8"
    "}#2yjP?4o~(hmBEA%ES|jq6A`Eqp6NyFs9+u*ku{ORL~CRu!f;Or51B>5HGoqj)(VG7hy!=PI6^9oak$ViKxp{dP"
    ">TtAqoWvA%TSg?rY=CSQvwy2we{3$?kQnf5QSNOodobQdV7cG`mH|DLhVan&pK2@+0?5(!SghjOWS?Z$rVsTk*QP"
    "k?t*)xf~z(0EVnDx!sU&C!4&lfSD%oxPR@S<71?+bH?gF8;lr>D3wegC924yjYFF>``b6jW?W^ZUTg@R<*A5%avh"
    "U7k^-rrAA3nSAF8p)w?ZssH#_ykE*t-k#`-^qXy2D-$)g9cTM|T-yV#PeI-3kTzc=Z!{JNawwczEY5!@E^>B{!mU"
    ">aeNFX$dcLNh+0IyzQRle|x@FOZ#@{R6fy_ro1;AHXK`ZsGZKR@UzoKcAr*yYyxvI-ld(>YKzYjO=_~ZYCbv{Hm|"
    "pN3BA|5DF^YIO^QX+>w$N}XuqM?g@>x6-(6p~>%zg{UQLT1)GdAhExv&Q*W~4GlEIWjy!b(Lo`KC(sg{x|W;xe=f"
    "AkKmH{RA6c@KX$J~})3{^Z@s`LF#Xz0;D_wMs3+n-7*f2ouk2e_(}>H&}kErRVq`M{mw2Y{L0OP2{92$MZVM%F{o"
    "f7ver8P=)HUC82Y1HCoC%jc&=Mbzo+ha8?H0g}e08LESL3Qgc<2vNvs4Zd|lW7iv0tyQEhKUeM91EW0qbAeMc9R?"
    "d8W#VybZ*{kJhnNjpOfp0s;2d7@`Tj&on4CrtHW3wUEdS3%GGEG|37?|YXfAiS|OgA_IR5s0ZJr)kn%4JaBI1V1S"
    "JSy`UhJHDJ_bW_sZ%(n#0&s%h|Ni9t(OZlO^X|i&|C*e<JzHpty9H?8YR=g+dv3Goxtce(DDm@x%+1w(IIvu&7#6"
    "bpJ~~bApl4nLU%C*C;2~-0yf8r-t#t}1LCHuqI$<&+B7C+c01#%%ZS<J1SYXCt8q3KPqeMt!Y37Vr9(<L9NXE#7_"
    "gWeT7#D;x0*cRl@bJ?psnaTWBAqS*HHH|yAzVbxB!x00nprY5CBsB^N~%CDH#$RGP-b)Dj8hh=;EKeOh{<q4NaVs"
    "fuBdVra54}@G0rvMt7Sq1|MKKq&Q92>1kuBTH4#9ZSdpAO+*E0wgtjF42wzB{bB^#ctQiHojfB$_sf4dE*E03a7^"
    "Xlr#O)Ea%IOAEvY*y#IZoqwdXXwW{K*fW-o2a9$=OdIP7(A(^?|5A_&=}jLAiJ8!FS=_T|hQn-&C{R3Y6_%07HEi"
    "VSOv%m(k9(x7Gk9eth@o41|E3{CM<n^7F}i_#0Y%etM6>rRebU;~$St(FUWJgsN=S0(h2H5A!^@t9fmRLCQZpJ5y"
    "Lmv%8#L;L!VTSdoi~$Gd9meK`I8<h&M5KYx06e)8tSFBlS<K10%8?(km!wj6TxIw*=wn4h+ExxO33uVU@~chfkZ0"
    "LM(5p7AgozKzFqed-jx1yJ4t{$2#z{<q7l=+^vt&(M8m7wU3^(YntyqrGfqfm*x1{)Sz*#?I|6O?xVOPvOWmi>-a"
    "zmaal~-ADIlhv(ZmP_Nr)T6$*t)H_o<puQd$p<cqZ(=cn;XW1%1)_Yl3(`B=@1n_i)<Fj4GW+g5bOtyfv*I!{G#Q"
    "@1wG~((huu{H1ezkUsVQ)JM%iOX5v$e1g+PlAX0Ly5*2G^4g4Djm&nkT^Q>FVsvIPDE4wrY~ZS)xkpP>=rJyRQ$T"
    "%c<jq!#Sn4uC03TeAgX@VnlOQ#~p7r7mh$eqSY3*&SWfHaD6^KIYM8UD$FaZUr2Ytf42SRMPDn8N>g@lYe(w7taI"
    "fI9;et6X};ACeLLg+{57y)Ey230qxe{+*kyYXl{Py){)onD@6V6QDf!9U^84CWAl^2a>@L%#PuKG=)34=tzuWkz8"
    "ox<${iVtZ*^^0f^#;n_vN!KGiSK#iW4HbLyKR9yZ$If>THtARMRxR%eyZ(}&i42vY>WgcQo;=oJcCY>aw{Yw!Y4-"
    "r<;mbqgQN@!D2>J((kx=m<%C-tR&w+~RRaEIsbvEHi4jU`t)`M=8fPtZFq|3Ty^C-aRH0bwD#6iD)tIuaER^MvG4"
    "Fj$j8d0^);fxW*1j4~@3RdCjRBIO1~f{fNmHsrWG2(7(4|-SV5E`Js9>{6CNLRo<}@?-fKh|#w1i5~-X49BDHKd+"
    "5|m?%NhfrPg%_dThPo^bRh}qEtdZIWMYWYK(V(ey30_@_CT5)o^_*KM8`MtP$2hy+vE%(^Xuc}X1819F*Z8#r-@="
    "!(X^DoY%c^=Xy}}+ayZ+X5Nh^Bluz}7YU{n&nbM{;c-up%B#VW1@Yjmir)o>*(2OC?hE&P1ph^Yw6_84jnRR0cq+"
    "6Q##-c@_Ty}me5nfUC>Df*dL_o{QI^-Wan&EWMD*DUgX3jfY^qGq#m=jM&0wGN$+y6^Pwefe6hBhouLT0S?A%3;S"
    "{*hs4}ubyXOXJ3rzc*_nN!qmiHL&y43(M$_V-EK7==hk#IPnYiMW*X-EJA`hWCVT#p&D>nDvBZYDa5Zls`m~dDJ*"
    ")M0QmUlGgH6H)r|VX_9-RZTJ#f(jIyi2-xq3GidakaG+tvDM_-E@NNsmcBBT?`om?tuz85s=A0416WW3<zhJ1?_g"
    "A^4DUPF8!yfPS<NHWKcfPLW!{vqx1dp!kFl9xT-?0yP=!Z4v+hPLoI|+$CBf;a8b>3e4ls$&)z>M3Ry!X@+AmQm7"
    "I-C<TLP!3kO~+n5sZ&Jr)2idJXgwDBww_!sa=3?$HONr{$hnc>z#BVlMDuUu3rD<K6B0)F5y)3NeUCQgi{$!ltmu"
    "MD1LCym&|g_M>=V}a}_6%s&31Y?qp((!;1&*4vshZwWsI$(Vm%><fE07GT<1kAIt%MH&@M{gb;1PwumvM?KFn*sb"
    ">N`Ys_;5|v=6!(r>=xHfR=p8&5>nT(eUP|PFnPMT{e?YVPEri9sD{9qpa(?UQUtLJ8lC5OqG6DNsT}eAgs~6z0?N"
    "z<rUi9-`;AH>nn|CF>R;8Yrt=Z#$oSdB(x1Qs(^P}(IVZ5Zb{g{$X<m}#Ex7~$*WM=I7lXSt~4qJP!ZOx$jp>``L"
    "!5)?sBf-O7S3Owz)Pwq7s}G<?BW({nxuN=NfU?t?4O#ZbBIc^@C-ZD@vb|yDev9F)w?M`#Jin-nAeWB2+JCpzI=G"
    "Slpa;75$#L9?)_N@V)E54z?b~gKd(OOB*I}a<?z+?2ju2b$>}j_r+Mjt8^sHhR+{tNn21NH|7OL>s1>@2(I(-qDj"
    "B&V)U~SckHJ=P!Y-@MnX5Q}~+Rf11ZBn&C2{8n0TAg*~=~YEz3l6iRyu?d3lo|l;d+1)&;i87KSDm|f)r7TlejK~"
    "_woBlURrwxRb#dfABC#&+UEYmb$CY?F^g3>Vr(xK!c7H}ByH1+C2&@$Vvk~)eGtQ*TkpMeVZL~5fW*@8<+>uOy79"
    "EW`M(2SCDOZ^rG(+aay4acsM9Z}zIT0sB;3@@WB}JS}4r<^D5g3<;K$Q$h-UhUMR>CBMhiE+T2o;BC0i;?jX@&<R"
    "$CE@G=TummAv+Vxs1mL^Q*%x@KyE-xxCM!V(%>8h0RkYGG;+*83~dR><{c9<W(jRhy-W^@19Y9Sc>$0WvBgZ<0aZ"
    "Jhj8lp$sWScmUJhV7p^7RJOm@*wX$_IeK#_e8+ymueASTVo6JYIj{jcv0+e<!*!vW^>X=u{^)Jq<&7SroXS8ZBe#"
    "j>x8GtKoBJ!1l_SxtzV64IeF45=(y`unU^EW&3O1GacXJvjL9nt`caw&#=D2!0QtlD6wGcXzE_3yE!?f4$}Jwl{O"
    "!@Z5(%&K;a`YZ-v7v^?r;oNYX<ti@ZWB`<nMg+==H`_46p$?M<UHGorxOM3^*k(RjwTDCu}U+&98%f2Y?r#WBm(z"
    "{`sWEoXHzYU!AA)wGLq8Fuf;2wD&8tnyjI)>i%sdVAK+wacjp^rkG(@V5^#a5~JbgO;bkEb7gIC*#6CP-QqbA9OL"
    "RDukSZdv>ee0{1KD)5;n9KOZzw5`p(voyoH3~#?4oW;z#?l8r=cMxE{aUY(~s;x7$ZLN&j%UtytExfB^+oo%#hIg"
    "v~c42xQZZF*R<jd?LLc8vEZre{oRQJVk<XeX~|2;ub5J~~9k;6xe?Z{+zb~OqHJg7)r(8@yh_t_v7QZs?quc*v1S"
    "gtwF)RWFLdpu3{#&EH}tzT->lRmva!Fe3RS^aSGkEPwGibshZsB#mUygU98Q$?Y-@mbTG?r7LMgnV&F$loxBJ}~8"
    "P*iqgd^Ve46d2{~SHh4VHUrR9eC;cY5-@}0ZOY~|ca9^Sgw~ChJ&Bg_iP4V9egk+VJQXy&yh@(WbRs!27p|fQc=v"
    "ZOAstB;nEX^r6!$T5)^_pp&bjU#H*<k{ntfL5mQ$d6Pf-*@l?`ebwCKMfld+!7T9EV?N_!qarhCqSaRn#tW3MC-P"
    "Mn@<-If+0sCfJ5s3Y8r#2iXp|Js2T!g8RZRA|6p2>vU2vS{9Y^848I<)kFuzO^!So6^Y|q1tflxiPF+)VHFhEQ0D"
    "~vpW_CFwgQ+RLw(6CG<PELoS=EK4N}3aEe$&m{{<)=xQhOb67uTxgYN*WaaMlVtpE%+TQ;S?%%)+G6|cVI(#58?("
    "yZD-=zdqcXRBg=Eg|sNo@X!la>eoU{&yLwlVxc6n;EoJZ!RE~q49U1nm8vp6D%>7EcA9JU`lYFWEhKtCFzVsC;o)"
    "_s9==hg_b^-6X+d0fw$uQK`hVyb?cLBtlL3&sI7oIxeBk|4XC#PhGDsSNdLeok{7hgow&aI@J~kdcl88b%ideL20"
    "#0qHS`Ydrtnp>^0V14SmM*WZ`6nWT4ig2u3C9TKj=0<+jfn6rG<a)!~9hi<$eyj|2oDjbZ<U<dVhX=I{Ep-+vCaU"
    "(fhYRm){@1gJvowXzgA>&&jnFI0JOX0#2IZQ~XOuw?lX0cF}AgdfEEF^Y#GTqQpkoHi_P=#pK8r7j;KP)G1Tj^s0"
    "o|zrlEmjqK?k@mFUJ{g{fS=eLpz=UN<Bw>9OqEi&j%tn{V_+ze=LywIy?=~eUD?RDkcT}6^?#mpXfq9^~BPb0%U2"
    "f5chhevl4-u7(azPk`F%XN6WR(a}uiT%41KkNp@%knEuObVYvG(s7krHC+p$V7pGJfJzu9BAM!D0c+2@LJ(~j0v|"
    "LY;r#6P?-V5kaOTVbCR9$(&S{lb>0Bvqjf&v$)Qg%$xuJs7H|QGK6!`fh6Qd-Xs<vpD;a%=KwwIGnsNKUQ^R-$G*"
    "eJG<t@vS{r~M<X>%J#lKm?PeVU0SW~-~Z>ySUeA}n)O61gPhnVpRZM4b|6K!QP#)@U~T-#4@R1kktv5~OK|Ws!Z="
    "nfYE;9?T28nrQ}&r&dsltq7R|X=jL&#z>zsiDnX$`am-!pnZuYiIY-7e?`g&rCH(x3dlsrj7I~BOH7hcbUa8Xyxv"
    "RYGD$R(!b^vN%qAh;1;Z%u(q=G)I#WS8ubI`FxR(=ea423C?V-|ZSySpLHH1ac(fs)2egEQe@Js*v<fjv?8FKpR^"
    "5p&J)6W-!Qn(yfMS63%xw(JF<Ct8Y(61x6xYT}`EpWwC5OEmKAJE;2z?KG31d<LmV@Py>#jcD|AU1-*M28}CuzwW"
    "@MkW&BSGK+U6P92se)#G0#~*uGwizH;|HI(($)`)64q}yROt*J_Q51OoaC-V*pU-kcy>G+K>VfC&Y_M`so<kO|^p"
    "~5_xQM)5X42W0iDr$^^F>CP@gZ1cb`v4qOv_eH^5NQE)~Nx!$kwr1>E9=_OCGJCMy?7s_#0y_u?CTHPDdI{f24WJ"
    "ykA?+==T2V8tpg(M8EKITpF;4t{;YYCIWkW5W}G#ZsM6bGOU=+5}ge|JB7i!KirOPBOCogk?3*&UA{(sgzG*3-9O"
    "6T{qczX@y$LgNE0#myS5$KuMan6#@H;Ozc0hlD(L}kM&IfQEfUwq8t;C_#G)%x(-7oUv@<!_EqB*fH@U@So@Yiw`"
    "iwU=E@4IEi~e9$8&f_M3-Sw08phg1Wf8RHd>n`hW{%@ffc~0eJ*%xg&E*F(caWB*9nixyEls=iZh6GS3(F6!wzV!"
    "jmt+jfM&hY0N(Y&sVI@HQEKEx9fs|uPI!{FqN;$%%Bn+fO#;9irvrKyKbw(_;A~=@N)Cofc%LvV68f#n=;{|0}V`"
    "@1XoFxiN$<b5_$D9s4gUiqdZk2I5VKRWAf)AwLlZ+rH<iSYmFmIet6ysvJpwek8xMwy&Yfup0X~`6}LgKgutb<LB"
    "#+PBv1!a@q6RJ|fNT#Ue2L7{xC7dP!9^*s>kp>aC_D(PsBx5v~z!ir##}FAFe8v=^N*Usk%sT}yPpx#;L+_+?8P="
    "e)p0mKv8YT#^V9F&?F2!Pc2V;p@l+2+50qxe1x13~0%{t!a{Y&6ZgWg3mHNY`&`16aCpHAN8D{iVp=)oF3n)ZPy<"
    ";f_l3z<03pgL&bvo!IVrGh9}#5@h!&_u)PPMmR)5@U?=i8LW&BuQ-=p48_A1Y{WrxMG>_MRtqML^$d6M;4UOTJ+L"
    "AB|Mnl^EHhbdWcB*fJ_?Oq$en&P-;8VOYt{ZHB~|TQfxIAJgy0^kzszd?J}KueverV+G%}DeuKw!48h<7th{zL92"
    "6Px@un=>N$^H9eE&W!P!trnhpynIuuJZNEV_wkiE*8}ph`JVyRQ|MEAsFAsY2g{7h79p$(Yz5UIV`zevgu(GDX%&"
    "cYZ#3k5u{e{22ahsN<hcKO7_1>>dBo`*hiR-!E(BlqQf*XzVD)d|`p{>Z8{l(^14WHU_E8o1nuzrsu0iqUp{unay"
    "E!kBzICxzqwI$us`nV6LYkFr~VweKjNtSn&=JZgT`0t-@^d!;!{LgSc!Z$ZV$s`O&jIta@;;Em_`g28hQatIs17L"
    "xGtV@l)WM#&QNcPRdj%E`v`wR%nxg6KOK8FuOs<kQjNz8J1%sHp71<$+Vf_r)O-C>yg2apa3TFjD5b0d2|+gKBz3"
    "UhDxd!bJC}YQw~0yDghi4s2NGPvEFc{6_7_f_ve&lRv?+<nZ))aJQap%1|3P65SDnZfv#$3wxYlVjgrh!6*Rn>gJ"
    "2+mCqO@yCek??OU=2II?sU^WRzPHLa@{%$|cliUSZov22>Mnppp<ORpPkehGi@hoC|@;AVh#(1S0~P+-QO+C9*VC"
    "KsgM9b{qJs<2DO{D5JSDQprRRpJoZtTeJFU{}v2vHD~`hL~As3MOC`HJe|@1a&nYV^7s7O)X_&n6}BbJ*@`_~r`="
    "mNS&6cRIIJGp|1s^Ju}%vin)Nx(Z=LT`oL_G%KQwWr1+LCzOq=$0S%iMWSD@xbldz^C(+ffF+o;h>BA}HabpU0+0"
    "-J%xSL04AF*@qtL-Aaolk>rDG4`E_35hA2#z!69THz^W_<_CE;A)IoF*|>PivZszJc5@*&ClW1Aoin5>40F+PT%X"
    "g4EAh5eN9s)1_yg~k65ME2(V~a8&A&X{&OFx=uy5E7M9^E4rZh9E2<q89z}Sp3X%xke|3Xm4tt9FG_M|s3?VM5!L"
    "9y|5U%l9NtNQ~OY##}Y?B`qE4D4jK96pWJf`vM>8g}F<WTut0Ga1-zs+gV{5;<{kytDMCIM*LjT;xP-T-J|ar$vf"
    "N$JK=M1u+_gEy-lC$;R1+5Phr;nDN$Pfbj`R`Z|DdC|PS@AAlKHMRB>wVgLoxX%f53mP)Qs7;AuOsSLylHdUf0|@"
    "R?LICPoJP6ULq#02ugXSghCrbsF!eAAnln8AAPaD{Eo>7+>t4W%1OnH_-mx2Z;EhtHd@LEF8MFNc6dd2~ra~AVAO"
    "Z1yfg5qBKOt2)Ambjn;bD34%5*Q(9rXnm$6eV7yne_<BeTEUwI4U9Fz;eP|DySDM&)gOgnJK9=lX{7P)j|PYXM{-"
    "@?gU+tB>;GxaE2QM9gt}%ZO|GIgAxL;o>>k(fl<kfa6mk~%shdPN++F&QP<j})C!wMpJzft!ZXD}qEZKwDM*$&qf"
    "^EL6FSQrHryCIaKiDkSsJkLlMDeV2w%g`_wKqX#5m;)Ye%CyhxV7srGOtjJyUq|R*?f`2l<6UbC2%2pyayW^zfhE"
    ";yhq^U~elGh&8b%-rVXc*G?l^_`(VveOnTT6$WDEFyDiq6f@)t!G3K3J!&HaDl&zBHB(HG4#3D7b>~zfGM1?s$>q"
    "Ktc5+;f#G;{Uo`PAd8o9fSksdt`F>alXVvkLCWeZlY7Wi)~gL}9v0G8C~VcfE{VygA=-~q7l;C?j73!=u@%sgDPX"
    "zAuGqFB=PfhJsqz0<f>!2WmzCU!OM(eMGRUR2rtOa4)e_bdUaiAhdHD!}LN^fwsiZ`Gn%HM(*&l)r~~%1v!Q>r<3"
    "Ni<#W4=Z{ZNp0v#BZZ!OJqAoHdlo`T#DjZM~0%V2w6jQ?xDN-g4!#qsfCf+iiS#21Fh7!zHtbya88?H_hE|g$SOX"
    "{o(G@;H>s$B+j0b?gqZ$oB{LmxCtMTUO1&XH87E(NlI5HAJJVwi+}8|x^rk3bxETsp;w#(Jw<2+ETrVL=fIq(U>{"
    "6%YcTBraAGf>+|Pq(Xl;@2$dgOWGw_${gOUOmLFYz!?Fi0WddkL6~&{-mIa+$iaZD=!EGcal~j~Zk$SG1Ch}7EEt"
    "tJ$|TdN5Q)}Vk{Rzc&>r}!G|=Lh_*p1uzt-LXA0b%AiP6Mlv8t?BBIUwZOKAerDV>pqOC#WJiNTzj!aFvkE@m{k#"
    "~pJEcz#0Cwk2PB8fvqy8`>1-d3u6Veydw3)w>0ZMv>0d^>v=vVbU&({pvJBrT`c;v$5t=UAmV=Km6jRykT=ZW$*^"
    "80cGF_?Sa&^b$%|3!6<=pn5&y$Ca;Duc1)2RN0ff^zTus<3(hi)nM(~48Atw^PU!^JMqV<}`OgXJBHL)o^mH5^ZC"
    "M`lwhHlXrP~XM_DVr>t;1flXLh9*au3<cE?G%?Dbz_m@(d0i@|dYc%p5GJxWzy>&<O{rS~b*QpcJxn0RfTo2uLQ{"
    "2}m4;h7<9W@Sl!RDnqb9G(`T8J6h#ZBKnFIJf@zccz$v->2sCK&iX*50DEOF{2d>m<QFOw7~6>`a8TQM9*M53U~y"
    "WXzbx(E^B^=!$L8@F&QkhtfRtxO|34>=<2*MuV=1wzW6UCwPk}>VxfUs$1GWS0lR#*IjNspF@XP|42*8b!#2~Jh_"
    ")p?BG#zfT%<>R81zI4Sf<77+v`_)CJ#&WAOj1vSmRh<1e`tnLNG>GKsg#<41#C>FnE@^l68J{2LebQ!EVD@#q_B7"
    "xgoi+wO$J(#O3m?vhhurz6fP5*62lXfD1`(lFyl!kpie>iz!T3>>UnB|R+xUmFdIyg3QUkil1!P@aRToIP9&4eDo"
    "mfteU=y?bpd*Ay!J$7SY=gkn8lQ5n#&{xVC{lwt;%uoXzU@-kNdB0-eygj0}o=DEQ%AFJ3$}F+042;<?Cp8U6gAr"
    "VrDU7dmZ+YM<WC9Y}Rx@^$S?njusxg`~xF<JJ+LMVPLv(v^&)hcZwRaM{j<HCU&*^#{+80PC~n1zu%4k0*?XXHon"
    ";i@&J_I{W4iMqG(dX6Slm+^R5snlPGdCHnYND%%v^Wg-AytfXT~t<}Td8ToPJZQNKi-RS3gfkd|qzJ<nllRT9JLB"
    "#DvHMXQC!%ud5WFqsMO=f>VFxaUGXGux$Ve45!#r&vZSO;My98T(R(zL1?S<XJl>HAN6r7h%N7hyMASXW~M&3QI}"
    "nlN8D3krYnXJ|&5gu}B9}Yn`UBj>UXICd9rpPl_g(&&q`?R|Dm3Tj7yNMw<m_eO58sfn_uTGh4mSPYnlW{ZGdypW"
    "g42QPA%A`wc9F`zzaR#Nu@u$u4%y7--iHNBE%%_{X3m%!h%gy-q)0!tWoC4A8rYj)ShzS9gv6KeJ4bA(h-)ns5T2"
    "@g{Meq21jB$OXWiGHnP?jAE%V!FUJ%=hj)mxJWXr*0^OD!BZ9ufN96<H*`>7<w3O)^0Gk>H!;mjSs5^H;Ch8^R5C"
    "C;U@4|fU1qLR>xj-7J@2fLD6V)1YSz3h_nmt6bxPcSRNXfo4GYha2Y^%c1w^4EkVIedEIgfvNNe~sA4IOxiA6^6>"
    "ROS*Ie%|MZ|Uf^UcGDc*yuCbDP&0Qn}hx9mhdq4S$C#-6+2Snl^Fy%$Dto*1Q&6mkYGJHu-5LHYHd{%2#?LhbkMa"
    "z1Qm9?vZt*^WG?5en>N_h1XlF?%^qAgq?!v#WFsSZzAzdsZ&qF$<o%z{w}c_2fJ_GCubO5Y-?FWwYhZ~&)0WZnxr"
    "w}y=cuuUr!n9J;>r8phIn!qQhm_f0nOR~xGd9FEhq)n=;F~m1k2`g!y)@Ln9dp>msm)*X-v&<x)I8E(Qp9sJG{!#"
    "PaZw}RwYT$X{Hk@VAENW5p;OqN^oL*2qsXP2?ve9OeoS@X+jcGit&q_bFUxKw!5T94HWly2=ji_z2)8dW8K@)@XC"
    "JQXImN&Z1WL1T%5c0f;@Ud6Xm^;j%($i_1;OrD0B^f)R~roVEnBJ&I-!8p+Y7ax|1qKC<Y;*g_@ZJRGSxA@XThMV"
    "rYSq&;&{~w8%JkGw3VE;92GbwAk8&ONN2Gj-U=Q4)b|am8L$m#KZp*ie`Cc4ao#&S;B;)DV54gAu||V_!SH?AvP$"
    "!MwaiqQbr-v$>F)cG)&1Dm}mg2L_f<srS|#`E@K>l`)>W(RsHinrf2M|+9Kz;L(V5QNUxT+fTJ!)XZ*O@x@U1?H}"
    "9z4bjISlj*AvI?x~Hx|MqvIE~bxI*Qw=K+Wj&d8R#W$X-r#Ni<8bbeRUsUaRG`O0^p2w&UzOYT{Qi6&eF&l7U6t7"
    "{HDK;2iVTR7fe2T6D!)r>=#=?`gYu#TW)9V+}Ltk*>D@a_CG{BZ?3m0184^mn&zhQqfRb-bDMC#Ug?!3cpTriKPz"
    "y<s+gP4CgtxUZm<ZdG?+p)UY||}7ni*sKlED+^Y!p8@uwG4#&yNu=W-c$62(>fV{GcNbn-EQu8_^~ub)h(p3J766"
    "t$JPKJKVTaC-Ku%t#FxllykJ#Pz~x_PghOJhp;inl5?uYgN;@mQ5Ses4?K^o0v<wc2CFbI$v6RM@p;hgvl{qKC!+"
    "u!2J8s;Fb^a)jcR3?sBJnKYK?^;djyRoxl4TQ_r6MrGJbWl0TltJsVTc_K%w{m@@UgeRJG<UoOG({(pZyIfwfv=u"
    "kqIS%8;sg&o;@mtdY&>+Z6~t!m4S!??F}G`aA<hF{^1@5T}uwyE~Y5c;lmm{1%*eT4@>P=D<AE<T^<X^63e#(D4E"
    "<=_|kwm6Py2c{d5yv40-vOe4^wc-7MQ7B7wssg|>EXK<f$J#X}lc{C`TEUYH@R~4E2WkM-X$QD8Sn6G{UNf1AHT<"
    "88kK+W4(d~I6a4x2Q&#}ud^v63;$zNMwMy0$)<2udX1iUcu(P*)G^RajS{^S#=3s4}JC-3Uy`S`*3#!c4V+lDovA"
    "&n<36m`<9iJN8wZ~68?`Syt{Tx&wc#U05<rpi~*t^9ZAqsYx?;;3lP{O>Q?xl<GO_OgHe5r4)Bu3$?6=McwL2gpB"
    "k(4X>4{>3WuMyDLy&YB?a2I%W<#<)FDGf(4EmZOLozmja75L3J~&hje{fEsMaEH4N=rba9`ouiDKa3Xl5<d@|D<;"
    "9R}6SFK$Zn<AwaI}pS&qFWk4$tP}(?l~atWr+!lw0k9DO2N=^@h0236{#lI$?o~XWRrrO-eM}trAIy%FLTNAE>1K"
    "obFA!9Q;DN<#Ooe%b|-a`VxH&ddH_{6&~E`;J=XD#W6pff`XGoy#(`<LU+fqVMQ}GA|rIEn7>A6WO5V3<!5y31Gq"
    "I8^(>lOx6OMyrr!qR?Rv^zan%;M>O3l^r$txo3Udy`nn6$N<0H^ew<EN@RBftEdGnM&m3e7(oV4!9E=Nn{z^t)L%"
    "CdqhfTr4&D=O1GA6@iV+zDXXX3*P#Q(nuZ(e4=lblga!SE`@Gfj@Qd+#(dTYw&!?_yw&KcV))+N}a?CL;q7%$Xtq"
    "Z%0%AX{J}k-oT7y*0-0^LZS}3jXkbE){(1j+Fgq{{;MekG&Qfj;mkOOQyR^4;71)q!t%aNBH2xsL(;_iiZnf^OY-"
    "5wyet_LJTi}q33&q56E=jT=gbY?BUJ;V2#KI5CT1G%-QZ5BeGO37xyID*!ka;Gw&Gv%tE{hfNu~;A{<@z{|>U3kM"
    "ciI1Vc8cdN)l8jydY4b+0@$~)+OOGqnS!$ss+Jh%GldarnKCvtMkwy^d^`)D1)@`<v0xL2DUcNIqMUh=3agFFm|@"
    "jRF+?(UuK(AwUhX@Um#jPe)E|84y&s&yGW^gx8(f}zxEy@^(9etY%{?2=3lYX@3g7hI^~3ETPueiV<wB2Oas0jQr"
    "n}L%QoBg3fHw#3mL7>s*S)COaPl7u39pk+dbf*l8o$P~UIc<wmaKd%I=A}%Yv&q(Yd$@lS}WE$9DeBBj5=qf@_!0"
    "+J3ElGFjo(Uo#9oC;A-lX;-L8E9}hS2TnENsj1|WbnLZM}EjwK6)vCiw0PXHH*q#~F^Re`mqPdZ+dE>L(2W$Np)<"
    "+RcGgnSl<92#}`Sa=f)2I+GQVgRzIsObkR3bB;@&9!4*RoDarAYqLJO79k&uI<|F-<^G^e0z1=e<uCCq-@acfH1g"
    "XT5VAlHP}t-UV*a%iiE`{qxho1s#Bh&1E!tVd_D+!pf<?j{e!`VsQn)@crPc{}<MT{}=fax&043$S)-_dK1C!8&9"
    "W4lVS--Ua&C+b54q8(>iYsmbanVv!HqN&Ky>N&{hMpd!W2ED0;=jJHo_glS=r<hZ{HahYyjb)9t-t<%7h^lShXeB"
    "IWIu=nDhR)1&$do0lo}9ci8Ch=^NK7{5Z}Jwao>duY5Mned}x<fXZVchkL>fSUK5jCiMj>D31Q;_&`cLGlSy()3-"
    "ZfC<*)u5+Yd6<z4?X!xtY8(@vsB4p_mz&|m7-^fLFE_(mj>*4*^-j^@1SYh-UxP9?sReRQc^c}38n4tF~;)SWF=D"
    "PAOp&<FdzpJ*(I&LisUwu(gjGsWR!e(l`c^e0a1^d2shB(^!c7GXcYYh+PSE@A!AMW0^^ZPyQ$V*wG#?(N;ZX>;z"
    "a&Kw7rxD}z>GTqINAJVu7(`f*B>ZLX-MjwTWs6r)#US7JE+@0HjmB3om?{R3mH@HT-{tNe;O=fNuK#;e)X^>)p9d"
    "SiYLBJXtFLhkkg8%5jip1jNTED+AM()PEoc2{I?x1ZG4l$7$rYz$!&Q8cGua|%mWD~~uRXs_3!Dh7=SmwsyPMLP#"
    "hEUf?QG5{u-{&dYZ&HIzz$nV(!u!Z=F1Rz{4HXhTu<yW8fHbTyDzg}wtKVRm%Pl)Y_`ltHTq2-H0;FWH`%op6ri)"
    "xDtt9$Jz=oUUTtB^gLqy|TYEEYMV*Nm*{<BffrK+1xFuxc5&M0ZK=!BtUSI@L!~b%Jp+`H8F<LY^8^;^H9*Iw5<C"
    "P+<(%nGjeMVhvYbxFtEI+4cthrj`S%+e+Bq<IU$)|}^L~)WD8N4S}iA+iBR7e1@2jx5`iQ!fSfbuHEDzQ=~SgkfA"
    "A(d&m7bO2@Tq@_qO4(IR)}K#d+1EmJ6*#{c@LA+x%4`T33!XSDSV&W<WkxI^8h8^E-t#mFO(dl@I0qx{gpmR$RvJ"
    "<-LP!>&_#Nww-!0%@FKTONYxN~Dfae{rmE*Irw=4629Vxh@M^j7B$VW8_@12BfJrn;>wgmOgTceK=H?^@nU>4_Y*"
    "o}kp{oHU!b`NH^gDkH=br(Q&DhlP05$hVkQLoVT@S*EEK~%e6yDtgBKIg!xUE|l)LZ-IUJkJh`?lf5HnSfHdV^F%"
    "6h^6hh>h>`8;A54x9i*oRuFpM6>D7$=lG(xIBl*3>RK4Q<!^Hg?#a>N-{*U@!SJw~MeOTS2+wVUD#=%xjIpa<~Q7"
    "^c{QF+15wP$@**Jsh~n|sqwyk`6OtBKd`E9PpRM3@b@+L0i50sQPmgjzikIhz+`wKD_Jelz*L9)UbnELYBMX9Br4"
    "3DtU4HXDU&t*n2ZqOFr*S!>PL<27}K0Ibbd+QH1orr}k)Yr~o$RpNj{s$%8Xk`)Z>*SpcpXgK;(RTkSr?9=XonpO"
    "dm`?3ipJGKe#A)IMj+yD0Vz!w|Hw0z~g8jYSXifK=Fr%mFQUd>34Z$_Fd5B_@&VVW6<-+{?sUlRQV1|^m5g@+rFG"
    "<RAy4@Y|5VL@aExO1N|L0cI#H$$9{9SyYU;q#O*-u+Q%@#eR^<KEfj$uIpuRrS9A;pF|vk01I63`<u9m8}47vh4j"
    "_<L%V51Al!rj!UM-9@Xxhi-s!Y-}Y1kqr_?Ra~Ik=u;%KfTqsy@5usDpz_YG%#yaQ4Xu)5iSeOrYTCj>9e$(H_9Z"
    "Xa8LkAjjci(}%WBu3B5U}~SRUONT>@J(3Zn*RQ-@X-}<h!O*tnIo+b*yqdf2B`U#BKnVTx_idOX>y>ZrQYR%fRTn"
    "yQ@f)7om~KP2c1SEALqZ9yk75Q{)AhpIl`$6#5xM@2umKcle%ZN3HHp=l%ZQ`cZ>dy_zYMy1C+?9NuP)!2-nOXt+"
    "(Msku6>Ia!-)r4^Unl=8`Eyqf>1$uFMz?eD++KV#CWI{"
)
SOURCE_PATHS = (
    ROOT_DIR
    / "configs/research-os/m4-v2-marginal-static-historical-identity-adoption-source-v1.json",
    ROOT_DIR
    / "configs/research-os/m4-v2-temporal-marginal-increment-source-v3.json",
    ROOT_DIR
    / "configs/research-os/m4-v2-joint-residual-increment-source-v3.json",
    ROOT_DIR / "configs/research-os/m4-v2-global-routing-source-v1.json",
)

EXPECTED_ARTIFACT_TYPES = {
    "M4V2BranchDecisionArtifact",
    "M4V2BranchDecisionReplayArtifact",
    "M4V2TemporalMarginalIncrementDesignArtifact",
    "M4V2TemporalMarginalIncrementPreregistrationBundleArtifact",
    "M4V2TemporalMarginalIncrementHealthAggregateArtifact",
    "M4V2TemporalMarginalIncrementHistoricalAggregateArtifact",
    "M4V2TemporalMarginalIncrementCandidateModelArtifact",
    "M4V2TemporalMarginalIncrementProducerCompletionArtifact",
    "M4V2TemporalMarginalIncrementScientificFailureArtifact",
    "M4V2JointResidualIncrementDesignArtifact",
    "M4V2JointResidualIncrementPreregistrationArtifact",
    "M4V2JointResidualMaximumEntropyBaselineArtifact",
    "M4V2JointResidualMeasurementHealthArtifact",
    "M4V2JointResidualHistoricalExecutionArtifact",
    "M4V2JointResidualCandidateModelArtifact",
    "M4V2JointResidualProducerCompletionArtifact",
    "M4V2JointResidualScientificFailureArtifact",
}

# Every numbered obligation in Request487 is intentionally mapped to at least one
# executable test below.  The matrix is itself checked so a future edit cannot
# silently drop one of the 45 frozen acceptance obligations.
ACCEPTANCE_MATRIX = {
    1: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    2: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    3: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    4: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    5: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    6: "test_marginal_identity_adoption_is_categorical_result_blind_and_singular",
    7: "test_governance_digest_equivalence_and_lifecycle_fail_closed",
    8: "test_marginal_identity_adoption_is_categorical_result_blind_and_singular",
    9: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    10: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    11: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    12: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    13: "test_resolver_global_route_and_four_and_p3_barrier",
    14: "test_resolver_global_route_and_four_and_p3_barrier",
    15: "test_global_router_is_finite_categorical_and_replay_is_pure",
    16: "test_global_router_is_finite_categorical_and_replay_is_pure",
    17: "test_global_router_is_finite_categorical_and_replay_is_pure",
    18: "test_global_router_repair_and_partial_positive_never_adaptive",
    19: "test_global_router_repair_and_partial_positive_never_adaptive",
    20: "test_resolver_global_route_and_four_and_p3_barrier",
    21: "test_resolver_global_route_and_four_and_p3_barrier",
    22: "test_resolver_global_route_and_four_and_p3_barrier",
    23: "test_resolver_global_route_and_four_and_p3_barrier",
    24: "test_p4_requires_completed_p3_and_explicit_pass",
    25: "test_p4_requires_completed_p3_and_explicit_pass",
    26: "test_source_contracts_exact_closure_and_digest_drift_fail_closed",
    27: "test_synthetic_cartesian_grid_seed_and_count_invariance",
    28: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    29: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    30: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    31: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    32: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    33: "test_acceptance_matrix_covers_all_45_required_goal_tests",
    34: "test_governance_digest_equivalence_and_lifecycle_fail_closed",
    35: "test_governance_constants_and_all_source_contract_seals",
    36: "test_successor_v2_estimator_identity_rejects_predecessor_v1",
    37: "test_fixed_null_warmup_exact_alias_and_falsifiers",
    38: "test_temporal_composite_and_joint_chronology_contracts",
    39: "test_synthetic_cartesian_grid_seed_and_count_invariance",
    40: "test_all_17_artifact_types_nested_lineage_paths_and_cardinalities",
    41: "test_holm_lineage_and_formal_one_rules_fail_before_workload",
    42: "test_global_router_is_finite_categorical_and_replay_is_pure",
    43: "test_atomic_publication_crash_reconciliation_and_conflicts",
    44: "test_engineering_boundary_has_zero_runtime_or_operator_actions",
    45: "test_resolver_global_route_and_four_and_p3_barrier",
}


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _manifest_payload() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _recovery_input_payload() -> dict[str, Any]:
    """Decode the immutable, result-blind recovery boundary under test."""

    encoded = RECOVERY_INPUT_FIXTURE_B85.encode("ascii")
    assert hashlib.sha256(encoded).hexdigest() == RECOVERY_INPUT_FIXTURE_B85_SHA256
    compressed = base64.b85decode(encoded)
    assert hashlib.sha256(compressed).hexdigest() == RECOVERY_INPUT_COMPRESSED_SHA256
    canonical = zlib.decompress(compressed)
    assert hashlib.sha256(canonical).hexdigest() == RECOVERY_INPUT_CANONICAL_SHA256
    payload = json.loads(canonical)
    typed = ControlPlaneManifest.from_dict(payload)
    assert typed.artifact_digest == RECOVERY_INPUT_MANIFEST_DIGEST
    snapshot = ResearchOSControlPlane().resolve(typed)
    assert snapshot.snapshot_digest == RECOVERY_INPUT_SNAPSHOT_DIGEST
    assert m4_v2_canonical_json(typed.to_dict(include_digest=True)).encode() == canonical
    return json.loads(canonical)


def test_recovery_input_fixture_matches_live_database_when_available() -> None:
    repository = PostgresResearchOSRepository()
    try:
        with repository.connection_factory():
            pass
    except psycopg.OperationalError:
        pytest.skip("configured PostgreSQL is unavailable for explicit integration check")

    typed = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    assert typed.artifact_digest == RECOVERY_INPUT_MANIFEST_DIGEST
    assert typed.to_dict(include_digest=True) == _recovery_input_payload()


def _successor_payload() -> dict[str, Any]:
    payload = _recovery_input_payload()
    for builder, path in zip(
        (
            marginal_builder.build_manifest,
            temporal_builder.build_manifest,
            joint_builder.build_manifest,
            global_builder.build_manifest,
        ),
        SOURCE_PATHS,
        strict=True,
    ):
        digest = json.loads(path.read_text(encoding="utf-8"))["artifact_digest"]
        payload, dry_run = builder(payload, digest)
        assert dry_run["status"] == "VERIFIED"
        for key in (
            "existing_goal_deletions",
            "existing_fact_deletions",
            "existing_state_regressions",
        ):
            if key in dry_run:
                assert dry_run[key] == 0
        assert dry_run["import_performed"] is False
    return payload


def _without_manifest_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(payload))
    result.pop("artifact_digest", None)
    result.pop("manifest_digest", None)
    return result


def _task(payload: Mapping[str, Any], task_key: str) -> dict[str, Any]:
    matches = [
        copy.deepcopy(item) for item in payload["tasks"] if item["task_key"] == task_key
    ]
    assert len(matches) == 1
    return matches[0]


def _dependency_tuples(task: Mapping[str, Any]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (
            item["dependency_type"],
            item["target_key"],
            item["required_status"],
        )
        for item in task["dependencies"]
    )


def _set_task_completed(payload: dict[str, Any], task_key: str) -> None:
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    typed_task = next(task for task in manifest.tasks if task.task_key == task_key)
    task = next(item for item in payload["tasks"] if item["task_key"] == task_key)
    task["status"] = "completed"
    task["completion_classification"] = "COMPLETE"
    if typed_task.requested_capability is not None:
        _add_facts(
            payload,
            mainline_completion_fact(
                task=typed_task,
                execution_id=_digest(f"completed-execution:{task_key}"),
            ),
        )


def _add_facts(payload: dict[str, Any], *facts: str) -> None:
    payload["facts"]["artifacts"] = sorted(
        set(payload["facts"]["artifacts"]).union(facts)
    )
    payload.pop("artifact_digest", None)
    payload.pop("manifest_digest", None)


def _resolution(manifest: ControlPlaneManifest, task_key: str):
    snapshot = ResearchOSControlPlane().resolve(manifest)
    return next(item for item in snapshot.resolutions if item.task_key == task_key)


def _registration(
    artifact: Mapping[str, Any],
    *,
    task_key: str,
    execution_id: str,
    slug: str,
    filename: str,
) -> dict[str, Any]:
    record = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=task_key,
        task_digest=_digest(f"task:{task_key}"),
        artifact_digest=str(artifact["artifact_digest"]),
        artifact_type=str(artifact["artifact_type"]),
        schema_version=str(artifact["schema_version"]),
        artifact_path=(
            f"runtime/research-os/mainline/tasks/{task_key}/{execution_id}/"
            f"artifacts/{slug}/{artifact['artifact_digest']}/{filename}"
        ),
        parent_digests=tuple(artifact["parent_digests"]),
        git_commit=GIT_COMMIT,
    )
    return {"registration_digest": record.registration_digest, **jsonable(record)}


class _TrackingIdentity(dict[str, Any]):
    def __init__(self, value: Mapping[str, Any]) -> None:
        super().__init__(value)
        self.reads: list[str] = []

    def get(self, key: str, default: Any = None) -> Any:
        self.reads.append(key)
        return super().get(key, default)

    def __getitem__(self, key: str) -> Any:
        self.reads.append(key)
        return super().__getitem__(key)


def _marginal_pair(*, evidence: str = "NEGATIVE", health: str = "PASS"):
    evaluated = health == "PASS"
    accepted = evaluated and evidence == "POSITIVE"
    categorical = {
        "measurement_health": health,
        "historical_run_status": "COMPLETE",
        "historical_evidence": evidence,
        "accepted_for_downstream_baseline": accepted,
        "accepted_model_artifact_digest": (
            marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST if evaluated else None
        ),
        "baseline_artifact_digest": (
            marginal.MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST if evaluated else None
        ),
        "baseline_source_model_artifact_digest": None,
        "endpoint_digest": _digest("marginal-endpoint"),
    }
    decision_execution = _digest("marginal-decision-execution")
    decision = marginal.build_marginal_static_branch_decision(
        categorical_identity=categorical,
        producer_execution_id=decision_execution,
        parent_digests=(
            _digest("marginal-source"),
            marginal.MARGINAL_STATIC_GATE_ARTIFACT_DIGEST,
        ),
    ).to_dict()
    decision_registration = _registration(
        decision,
        task_key=marginal.MARGINAL_STATIC_DECISION_TASK_KEY,
        execution_id=decision_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    replay_execution = _digest("marginal-replay-execution")
    replay = marginal.build_marginal_static_branch_decision_replay(
        decision=decision,
        source_contract_digest=_digest("marginal-source"),
        decision_registration_digest=decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "marginal-producer-execution-artifact"
        ),
        replay_execution_id=replay_execution,
    ).to_dict()
    replay_registration = _registration(
        replay,
        task_key=marginal.MARGINAL_STATIC_REPLAY_TASK_KEY,
        execution_id=replay_execution,
        slug="branch-decision-replay",
        filename="replay.json",
    )
    return {
        "decision": decision,
        "decision_registration": decision_registration,
        "replay": replay,
        "replay_registration": replay_registration,
    }


def _zero_compute_records(*, marginal_evidence: str = "NEGATIVE", health: str = "PASS"):
    marginal_record = _marginal_pair(evidence=marginal_evidence, health=health)
    temporal_execution = _digest("temporal-decision-execution")
    temporal_decision, temporal_completion = (
        temporal.build_temporal_parent_not_accepted_path(
            source_contract_digest=_digest("temporal-source"),
            preregistration_artifact_digest=_digest("temporal-preregistration"),
            marginal_decision_artifact=marginal_record["decision"],
            marginal_replay_artifact=marginal_record["replay"],
            producer_execution_id=temporal_execution,
        )
    )
    temporal_decision_registration = _registration(
        temporal_decision,
        task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        execution_id=temporal_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    temporal_replay_execution = _digest("temporal-replay-execution")
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=_digest("temporal-source"),
        decision_artifact=temporal_decision,
        decision_registration_digest=temporal_decision_registration[
            "registration_digest"
        ],
        decision_producer_execution_artifact_digest=_digest(
            "temporal-producer-execution-artifact"
        ),
        replay_execution_id=temporal_replay_execution,
    )
    temporal_replay_registration = _registration(
        temporal_replay,
        task_key=temporal.TEMPORAL_REPLAY_TASK_KEY,
        execution_id=temporal_replay_execution,
        slug="branch-decision-replay",
        filename="replay.json",
    )
    temporal_record = {
        "decision": temporal_decision,
        "decision_registration": temporal_decision_registration,
        "replay": temporal_replay,
        "replay_registration": temporal_replay_registration,
    }

    joint_execution = _digest("joint-decision-execution")
    joint_decision, joint_completion = joint.build_joint_parent_not_accepted_path(
        source_contract_digest=_digest("joint-source"),
        preregistration_artifact_digest=_digest("joint-preregistration"),
        marginal_decision_artifact=marginal_record["decision"],
        marginal_replay_artifact=marginal_record["replay"],
        temporal_decision_artifact=temporal_decision,
        temporal_replay_artifact=temporal_replay,
        producer_execution_id=joint_execution,
    )
    joint_decision_registration = _registration(
        joint_decision,
        task_key=joint.JOINT_PRODUCER_TASK_KEY,
        execution_id=joint_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    joint_replay_execution = _digest("joint-replay-execution")
    joint_replay = joint.build_joint_branch_replay(
        source_contract_digest=_digest("joint-source"),
        decision_artifact=joint_decision,
        decision_registration_digest=joint_decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "joint-producer-execution-artifact"
        ),
        replay_execution_id=joint_replay_execution,
    )
    joint_replay_registration = _registration(
        joint_replay,
        task_key=joint.JOINT_REPLAY_TASK_KEY,
        execution_id=joint_replay_execution,
        slug="branch-decision-replay",
        filename="replay.json",
    )
    joint_record = {
        "decision": joint_decision,
        "decision_registration": joint_decision_registration,
        "replay": joint_replay,
        "replay_registration": joint_replay_registration,
    }
    return (
        (marginal_record, temporal_record, joint_record),
        (temporal_completion, joint_completion),
    )


def _accepted_records():
    marginal_record = _marginal_pair(evidence="POSITIVE")

    temporal_execution = _digest("accepted-temporal-decision-execution")
    temporal_model = _digest("accepted-temporal-model")
    temporal_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        estimand_digest=M4_V2_ESTIMAND_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        scientific_decision="BRANCH_INFORMATION_ACCEPTED",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="POSITIVE",
        accepted_for_downstream_baseline=True,
        accepted_model_artifact_digest=temporal_model,
        baseline_artifact_digest=marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        baseline_source_model_artifact_digest=(
            marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST
        ),
        producer_task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        producer_execution_id=temporal_execution,
        parent_digests=(
            _digest("temporal-source"),
            _digest("temporal-preregistration"),
            marginal_record["decision"]["artifact_digest"],
            marginal_record["replay"]["artifact_digest"],
        ),
    ).to_dict()
    temporal_decision_registration = _registration(
        temporal_decision,
        task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        execution_id=temporal_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    temporal_replay_execution = _digest("accepted-temporal-replay-execution")
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=_digest("temporal-source"),
        decision_artifact=temporal_decision,
        decision_registration_digest=temporal_decision_registration[
            "registration_digest"
        ],
        decision_producer_execution_artifact_digest=_digest(
            "accepted-temporal-producer-execution-artifact"
        ),
        replay_execution_id=temporal_replay_execution,
    )
    temporal_record = {
        "decision": temporal_decision,
        "decision_registration": temporal_decision_registration,
        "replay": temporal_replay,
        "replay_registration": _registration(
            temporal_replay,
            task_key=temporal.TEMPORAL_REPLAY_TASK_KEY,
            execution_id=temporal_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }

    joint_execution = _digest("accepted-joint-decision-execution")
    joint_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id="JOINT_RESIDUAL_INCREMENT",
        estimand_digest=M4_V2_ESTIMAND_DIGESTS["JOINT_RESIDUAL_INCREMENT"],
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        scientific_decision="BRANCH_INFORMATION_ACCEPTED",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="POSITIVE",
        accepted_for_downstream_baseline=True,
        accepted_model_artifact_digest=_digest("accepted-joint-model"),
        baseline_artifact_digest=_digest("accepted-joint-baseline"),
        baseline_source_model_artifact_digest=temporal_model,
        producer_task_key=joint.JOINT_PRODUCER_TASK_KEY,
        producer_execution_id=joint_execution,
        parent_digests=(
            _digest("joint-source"),
            _digest("joint-preregistration"),
            temporal_decision["artifact_digest"],
            temporal_replay["artifact_digest"],
        ),
    ).to_dict()
    joint_decision_registration = _registration(
        joint_decision,
        task_key=joint.JOINT_PRODUCER_TASK_KEY,
        execution_id=joint_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    joint_replay_execution = _digest("accepted-joint-replay-execution")
    joint_replay = joint.build_joint_branch_replay(
        source_contract_digest=_digest("joint-source"),
        decision_artifact=joint_decision,
        decision_registration_digest=joint_decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "accepted-joint-producer-execution-artifact"
        ),
        replay_execution_id=joint_replay_execution,
    )
    joint_record = {
        "decision": joint_decision,
        "decision_registration": joint_decision_registration,
        "replay": joint_replay,
        "replay_registration": _registration(
            joint_replay,
            task_key=joint.JOINT_REPLAY_TASK_KEY,
            execution_id=joint_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }
    return marginal_record, temporal_record, joint_record


def _partial_positive_records():
    """One valid positive ancestor plus an inconclusive Temporal and stopped Joint."""

    marginal_record = _marginal_pair(evidence="POSITIVE")
    temporal_execution = _digest("partial-temporal-decision-execution")
    temporal_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        estimand_digest=M4_V2_ESTIMAND_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="INCONCLUSIVE_DUE_TO_POWER",
        scientific_decision="INCONCLUSIVE_DUE_TO_POWER",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="INCONCLUSIVE",
        accepted_for_downstream_baseline=False,
        accepted_model_artifact_digest=_digest("partial-temporal-model"),
        baseline_artifact_digest=marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        baseline_source_model_artifact_digest=(
            marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST
        ),
        producer_task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        producer_execution_id=temporal_execution,
        parent_digests=(
            _digest("temporal-source"),
            _digest("temporal-preregistration"),
            marginal_record["decision"]["artifact_digest"],
            marginal_record["replay"]["artifact_digest"],
        ),
    ).to_dict()
    temporal_decision_registration = _registration(
        temporal_decision,
        task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        execution_id=temporal_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    temporal_replay_execution = _digest("partial-temporal-replay-execution")
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=_digest("temporal-source"),
        decision_artifact=temporal_decision,
        decision_registration_digest=temporal_decision_registration[
            "registration_digest"
        ],
        decision_producer_execution_artifact_digest=_digest(
            "partial-temporal-producer-execution-artifact"
        ),
        replay_execution_id=temporal_replay_execution,
    )
    temporal_record = {
        "decision": temporal_decision,
        "decision_registration": temporal_decision_registration,
        "replay": temporal_replay,
        "replay_registration": _registration(
            temporal_replay,
            task_key=temporal.TEMPORAL_REPLAY_TASK_KEY,
            execution_id=temporal_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }

    joint_execution = _digest("partial-joint-decision-execution")
    joint_decision, _ = joint.build_joint_parent_not_accepted_path(
        source_contract_digest=_digest("joint-source"),
        preregistration_artifact_digest=_digest("joint-preregistration"),
        marginal_decision_artifact=marginal_record["decision"],
        marginal_replay_artifact=marginal_record["replay"],
        temporal_decision_artifact=temporal_decision,
        temporal_replay_artifact=temporal_replay,
        producer_execution_id=joint_execution,
    )
    joint_decision_registration = _registration(
        joint_decision,
        task_key=joint.JOINT_PRODUCER_TASK_KEY,
        execution_id=joint_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    joint_replay_execution = _digest("partial-joint-replay-execution")
    joint_replay = joint.build_joint_branch_replay(
        source_contract_digest=_digest("joint-source"),
        decision_artifact=joint_decision,
        decision_registration_digest=joint_decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "partial-joint-producer-execution-artifact"
        ),
        replay_execution_id=joint_replay_execution,
    )
    joint_record = {
        "decision": joint_decision,
        "decision_registration": joint_decision_registration,
        "replay": joint_replay,
        "replay_registration": _registration(
            joint_replay,
            task_key=joint.JOINT_REPLAY_TASK_KEY,
            execution_id=joint_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }
    return marginal_record, temporal_record, joint_record


def test_acceptance_matrix_covers_all_45_required_goal_tests() -> None:
    assert tuple(ACCEPTANCE_MATRIX) == tuple(range(1, 46))
    test_names = {
        name
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    }
    assert set(ACCEPTANCE_MATRIX.values()).issubset(test_names)


def test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history() -> None:
    before = ControlPlaneManifest.from_dict(_recovery_input_payload()).to_dict(
        include_digest=False
    )
    after = ControlPlaneManifest.from_dict(_successor_payload()).to_dict(
        include_digest=False
    )
    before_tasks = {item["task_key"]: item for item in before["tasks"]}
    after_tasks = {item["task_key"]: item for item in after["tasks"]}
    assert len(after_tasks) == len(before_tasks)
    assert marginal_builder.DECISION_TASK_KEY in before_tasks
    assert marginal_builder.DECISION_TASK_KEY not in after_tasks
    assert marginal_builder.RECOVERY_TASK_KEY not in before_tasks
    assert marginal_builder.RECOVERY_TASK_KEY in after_tasks

    revised = {
        marginal_builder.DECISION_TASK_KEY,
        marginal_builder.REPLAY_TASK_KEY,
        temporal_builder.DESIGN_TASK,
        temporal_builder.PREREG_TASK,
        temporal_builder.PRODUCER_TASK,
        temporal_builder.REPLAY_TASK,
        joint_builder.DESIGN_TASK,
        joint_builder.PREREG_TASK,
        joint_builder.PRODUCER_TASK,
        joint_builder.REPLAY_TASK,
        global_builder.GLOBAL_TASK,
    }
    for task_key, task in before_tasks.items():
        if task_key not in revised:
            assert after_tasks[task_key] == task
        elif task_key != marginal_builder.DECISION_TASK_KEY:
            for state_field in (
                "status",
                "completion_classification",
                "superseded_by_task_digest",
            ):
                assert after_tasks[task_key].get(state_field) == task.get(state_field)
    recovery = after_tasks[marginal_builder.RECOVERY_TASK_KEY]
    assert recovery["status"] == "draft"
    assert recovery["completion_classification"] == "INTEGRATION_PENDING"
    assert recovery["metric_contract"]["recovery_lineage"] == {
        "old_failed_task_key": marginal_builder.DECISION_TASK_KEY,
        "old_failed_task_definition_digest": (
            "6f21824945ebdf8e19dcd946ffbc6260f8e28fc52555a5060422f152d37677fd"
        ),
        "old_failed_execution_digest": (
            "43eed4c903a59595336b514f17c3be318714535e3b61341ae3a492f03fb4e488"
        ),
        "old_started_event_digest": (
            "dfae9cbce68c931b7e0b715223623a4e7691cbb2613b0f6ef3dbdb00deb550a3"
        ),
        "old_failed_event_digest": (
            "8291bed8402c539f416f9c8d8a23c2f59800ff544d7b5ca90a5f3878d6ef665f"
        ),
        "old_event_manifest_digest": (
            "79a8abb17bb705ab21350d6d3df882bbd39d89c3b7d2a3e9e5fa4f3c43046966"
        ),
        "old_durable_history_preserved": True,
    }
    canonical_keys = {
        marginal_builder.RECOVERY_TASK_KEY,
        *(revised - {marginal_builder.DECISION_TASK_KEY}),
    }
    for task_key in canonical_keys:
        integration = after_tasks[task_key]["metric_contract"]["mainline_integration"]
        assert "downstream_consumer" in integration
        assert "evidence_progress_rule" in integration
        assert "next_consumer" not in integration
        assert "evidence_rule" not in integration
    for fact_type, facts in before["facts"].items():
        assert set(facts).issubset(after["facts"][fact_type])

    p2 = after_tasks["m4-p2-synthetic-measurement-validation"]
    assert p2 == before_tasks["m4-p2-synthetic-measurement-validation"]
    p2r = after_tasks[P2R_TASK_KEY]
    assert p2r["status"] == "draft"
    assert p2r["completion_classification"] == "INTEGRATION_PENDING"
    assert all(
        dependency["target_key"] != P2R_TASK_KEY
        for key in (
            PREDICTIVE_P3_TASK_KEY,
            PREDICTIVE_P4_TASK_KEY,
            PREDICTIVE_P5_TASK_KEY,
        )
        for dependency in after_tasks[key]["dependencies"]
    )
    assert not any(
        "promotion:allowed" in fact.lower() for fact in after["facts"]["artifacts"]
    )

    structural_goal = next(
        item
        for item in after["goals"]
        if item["goal_key"] == "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY"
    )
    assert (
        "NO_STABLE_STRUCTURAL_UTILITY"
        in structural_goal["target_metric_manifest"]["allowed_decisions"]
    )
    assert structural_goal["target_metric_manifest"]["prediction_promotion"] == "closed"


def test_recovery_entry_audit_rejects_manifest_ready_and_event_lineage_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_payload = _recovery_input_payload()
    source_digest = json.loads(SOURCE_PATHS[0].read_text(encoding="utf-8"))[
        "artifact_digest"
    ]
    tampered = copy.deepcopy(input_payload)
    tampered.pop("manifest_digest")
    _add_facts(tampered, "unexpected-ready-enabling-fact")
    with pytest.raises(
        AdditiveManifestMigrationError,
        match="manifest_recovery_input_manifest_digest_changed",
    ):
        marginal_builder.build_manifest(tampered, source_digest)

    exact_metadata = tuple(
        {
            "sequence": sequence,
            "event_type": event_type,
            "event_digest": event_digest,
            "execution_id": (
                "43eed4c903a59595336b514f17c3be318714535e3b61341ae3a492f03fb4e488"
            ),
            "task_key": marginal_builder.DECISION_TASK_KEY,
            "task_digest": (
                "6f21824945ebdf8e19dcd946ffbc6260f8e28fc52555a5060422f152d37677fd"
            ),
            "control_plane_key": CONTROL_PLANE_KEY,
            "manifest_digest": (
                "79a8abb17bb705ab21350d6d3df882bbd39d89c3b7d2a3e9e5fa4f3c43046966"
            ),
            "capability": "m4_v2_marginal_static_historical_identity_adoption",
        }
        for sequence, event_type, event_digest in (
            (
                0,
                "started",
                "dfae9cbce68c931b7e0b715223623a4e7691cbb2613b0f6ef3dbdb00deb550a3",
            ),
            (
                1,
                "failed",
                "8291bed8402c539f416f9c8d8a23c2f59800ff544d7b5ca90a5f3878d6ef665f",
            ),
        )
    )
    verify_failed_task_recovery_event_metadata(exact_metadata)
    for index in range(len(exact_metadata)):
        altered = [dict(item) for item in exact_metadata]
        altered[index]["event_digest"] = _digest(f"forged-event-{index}")
        with pytest.raises(
            AdditiveManifestMigrationError,
            match="failed_execution_event_metadata_changed",
        ):
            verify_failed_task_recovery_event_metadata(altered)

    class _Cursor:
        def __init__(
            self,
            rows: Sequence[Mapping[str, Any]],
            *,
            current_digest: str = (
                "94f7e6448fa1572802a050129d09c8bd679772afc62f31f0d1dc2544d098c58a"
            ),
            current_payload: Mapping[str, Any] | None = None,
        ) -> None:
            self.rows = tuple(dict(item) for item in rows)
            self.current_digest = current_digest
            self.current_payload = current_payload

        def execute(self, statement: str, _params: object) -> SimpleNamespace:
            if "FROM research_os_control_planes" in statement:
                return SimpleNamespace(
                    fetchone=lambda: {
                        "current_manifest_digest": self.current_digest
                    }
                )
            if "FROM research_os_manifests" in statement:
                return SimpleNamespace(
                    fetchone=lambda: (
                        None
                        if self.current_payload is None
                        else {"manifest_json": dict(self.current_payload)}
                    )
                )
            if "FROM research_os_task_definitions" in statement:
                return SimpleNamespace(
                    fetchone=lambda: {
                        "task_digest": (
                            "6f21824945ebdf8e19dcd946ffbc6260f8e28fc52555a5060422f152d37677fd"
                        ),
                        "declared_status": "failed",
                        "completion_classification": "INTEGRATED",
                        "superseded_by_task_digest": None,
                    }
                )
            if "FROM research_os_mainline_execution_events" in statement:
                return SimpleNamespace(fetchall=lambda: self.rows)
            raise AssertionError(statement)

    successor = ControlPlaneManifest.from_dict(_successor_payload())
    PostgresResearchOSRepository._verify_m4_v2_failed_task_recovery_import(
        _Cursor(exact_metadata),
        control_plane_key=CONTROL_PLANE_KEY,
        manifest=successor,
    )
    PostgresResearchOSRepository._verify_m4_v2_failed_task_recovery_import(
        _Cursor(exact_metadata, current_digest=successor.artifact_digest),
        control_plane_key=CONTROL_PLANE_KEY,
        manifest=successor,
    )

    successor_payload = successor.to_dict(include_digest=False)
    successor_payload["facts"]["artifacts"] = sorted(
        {*successor_payload["facts"]["artifacts"], "post-recovery-state-progress"}
    )
    progressed = ControlPlaneManifest.from_dict(successor_payload)
    PostgresResearchOSRepository._verify_m4_v2_failed_task_recovery_import(
        _Cursor(
            exact_metadata,
            current_digest=successor.artifact_digest,
            current_payload=successor.to_dict(include_digest=True),
        ),
        control_plane_key=CONTROL_PLANE_KEY,
        manifest=progressed,
    )

    forged_payload = successor.to_dict(include_digest=False)
    next(
        item
        for item in forged_payload["tasks"]
        if item["task_key"] == marginal_builder.REPLAY_TASK_KEY
    )["priority"] += 1
    forged_current = ControlPlaneManifest.from_dict(forged_payload)
    with pytest.raises(
        ResearchOSValidationError,
        match="current_manifest_lineage_changed",
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_task_recovery_import(
            _Cursor(
                exact_metadata,
                current_digest=forged_current.artifact_digest,
                current_payload=forged_current.to_dict(include_digest=True),
            ),
            control_plane_key=CONTROL_PLANE_KEY,
            manifest=progressed,
        )
    drifted_rows = (
        exact_metadata[:-1],
        (*exact_metadata, dict(exact_metadata[-1])),
        tuple(reversed(exact_metadata)),
        (
            {**exact_metadata[0], "event_digest": _digest("forged-event")},
            exact_metadata[1],
        ),
    )
    for rows in drifted_rows:
        with pytest.raises(
            ResearchOSValidationError,
            match="failed_execution_event_metadata_changed",
        ):
            PostgresResearchOSRepository._verify_m4_v2_failed_task_recovery_import(
                _Cursor(rows),
                control_plane_key=CONTROL_PLANE_KEY,
                manifest=successor,
            )

    class _Context:
        def __init__(self, value: object) -> None:
            self.value = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(self, *_args: object) -> None:
            return None

    class _NoWriteConnection:
        def cursor(self, **_kwargs: object) -> _Context:
            return _Context(SimpleNamespace())

    preflight_calls: list[str] = []

    def reject_before_write(
        _cursor: object, *, control_plane_key: str, manifest: object
    ) -> None:
        assert control_plane_key == CONTROL_PLANE_KEY
        assert manifest is not None
        preflight_calls.append("preflight")
        raise ResearchOSValidationError("lineage_preflight_rejected")

    monkeypatch.setattr(
        PostgresResearchOSRepository,
        "_verify_m4_v2_failed_task_recovery_import",
        staticmethod(reject_before_write),
    )
    repository = PostgresResearchOSRepository(
        lambda: _Context(_NoWriteConnection())  # type: ignore[arg-type]
    )
    with pytest.raises(ResearchOSValidationError, match="lineage_preflight_rejected"):
        repository.import_manifest(
            control_plane_key=CONTROL_PLANE_KEY,
            payload=successor.to_dict(include_digest=True),
        )
    assert preflight_calls == ["preflight"]


def test_recovery_status_projection_uses_only_the_new_active_identity() -> None:
    manifest = ControlPlaneManifest.from_dict(_successor_payload())
    verified = validate_m4_v2_successor_structure(manifest)
    assert verified["status"] == "VERIFIED"
    assert M4_V2_SUCCESSOR_TASKS["marginal_decision"] == (
        marginal_builder.RECOVERY_TASK_KEY
    )
    assert marginal_builder.DECISION_TASK_KEY not in {
        task.task_key for task in manifest.tasks
    }


def test_global_downstream_route_map_is_exact_and_unknown_route_fails_closed() -> None:
    payload = _successor_payload()
    global_task = _task(payload, global_builder.GLOBAL_TASK)
    integration = global_task["metric_contract"]["mainline_integration"]
    downstream = integration["downstream_consumer"]
    assert downstream == global_builder.GLOBAL_DOWNSTREAM_CONSUMER
    assert hashlib.sha256(downstream.encode()).hexdigest() == (
        "5821fa0f008bf14548be0d2faa5d007e150d116ceaecbb39b170f0ca53917d60"
    )
    mapping = json.loads(downstream)
    assert mapping["ADAPTIVE_RESEARCH_ELIGIBLE"] == (
        "P3_PREDICTIVE_PREREGISTRATION_FREEZE"
    )
    assert all(
        consumer != "P3_PREDICTIVE_PREREGISTRATION_FREEZE"
        for route, consumer in mapping.items()
        if route != "ADAPTIVE_RESEARCH_ELIGIBLE"
    )
    assert "UNKNOWN_ROUTE" not in mapping


def test_marginal_identity_adoption_is_categorical_result_blind_and_singular() -> None:
    tracked = _TrackingIdentity(
        {
            "measurement_health": "PASS",
            "historical_run_status": "COMPLETE",
            "historical_evidence": "NEGATIVE",
            "accepted_for_downstream_baseline": False,
            "accepted_model_artifact_digest": marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
            "baseline_artifact_digest": marginal.MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST,
            "baseline_source_model_artifact_digest": None,
            "endpoint_digest": _digest("endpoint"),
        }
    )
    first = marginal.build_marginal_static_branch_decision(
        categorical_identity=tracked,
        producer_execution_id=_digest("categorical-producer"),
        parent_digests=(_digest("source"), _digest("registered-gate")),
    )
    second = marginal.build_marginal_static_branch_decision(
        categorical_identity=dict(tracked),
        producer_execution_id=_digest("categorical-producer"),
        parent_digests=(_digest("source"), _digest("registered-gate")),
    )
    assert first.artifact_digest == second.artifact_digest
    assert first.branch_id == "MARGINAL_STATIC"
    assert first.terminal_decision == "NO_DETECTABLE_INFORMATION"
    assert first.producer_task_key == marginal.MARGINAL_STATIC_DECISION_TASK_KEY
    assert not {
        "raw_p_value",
        "fold_scores",
        "historical_fold_scores",
        "prediction_results",
    }.intersection(tracked.reads)

    polluted = dict(tracked)
    polluted["raw_primary_p_value"] = 0.001
    with pytest.raises(
        marginal.MarginalStaticBranchDecisionError, match="result_payload"
    ):
        marginal.build_marginal_static_branch_decision(
            categorical_identity=polluted,
            producer_execution_id=_digest("categorical-producer"),
            parent_digests=(_digest("source"), _digest("registered-gate")),
        )
    wrong_identity = dict(tracked)
    wrong_identity["accepted_model_artifact_digest"] = _digest("not-marginal")
    with pytest.raises(
        marginal.MarginalStaticBranchDecisionError, match="identity_mismatch"
    ):
        marginal.build_marginal_static_branch_decision(
            categorical_identity=wrong_identity,
            producer_execution_id=_digest("categorical-producer"),
            parent_digests=(_digest("source"), _digest("registered-gate")),
        )


def _governance_fixture(identifier: int, *, failed: bool = False):
    request = {
        "id": identifier,
        "request_key": f"request-{identifier}",
        "request_type": "engineering_implementation"
        if failed
        else "research_scheduler_request",
        "requested_by_role": "research",
        "requested_by": "research:fixture",
        "hypothesis_id": None,
        "experiment_id": None,
        "parent_request_id": None,
        "title": "result-blind fixture",
        "summary": "metadata only",
        "payload": {"result_payload_reads": 0, "computation": 0},
        "status": "failed" if failed else "completed",
        "risk_level": "critical",
        "requires_review": True,
        "metadata": {"scientific_result_read": False},
    }
    execution_id = identifier + 1000
    execution = {
        "id": execution_id,
        "request_id": identifier,
        "executor_role": "engineering" if failed else "research",
        "executor_id": "fixture:executor",
        "execution_type": "isolated",
        "status": "failed" if failed else "completed",
        "environment": "isolated",
        "run_id": f"run-{execution_id}",
        "started_at": "2026-08-11T00:00:00+00:00",
        "completed_at": "2026-08-11T00:00:01+00:00",
        "artifact_paths": [],
        "created_at": "2026-08-11T00:00:00+00:00",
    }
    decision_count = 3 if failed else 2
    decisions = []
    for offset in range(decision_count):
        decision_id = identifier * 10 + offset
        final = offset == decision_count - 1
        decisions.append(
            {
                "id": decision_id,
                "request_id": identifier,
                "previous_status": "running" if final else "under_review",
                "new_status": (
                    "failed"
                    if failed and final
                    else "completed"
                    if final
                    else "approved"
                ),
                "decision_code": (
                    "execution_failed"
                    if failed and final
                    else "execution_completed"
                    if final
                    else "request_approved"
                ),
                "summary": f"decision-{offset}",
                "reason": {"result_blind": True, "result_payload_reads": 0},
                "decided_by_role": "reviewer",
                "decided_by": "reviewer:fixture",
                "decided_at": f"2026-08-11T00:00:0{offset}+00:00",
                "created_at": f"2026-08-11T00:00:0{offset}+00:00",
            }
        )
    return request, execution, decisions


class _Rows:
    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.rows = [copy.deepcopy(dict(row)) for row in rows]

    def fetchall(self):
        return copy.deepcopy(self.rows)


class _GovernanceCursor:
    def __init__(self, fixture: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        self.fixture = fixture
        self.sql: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql: str, _params: Any):
        normalized = " ".join(sql.split())
        self.sql.append(normalized)
        if "FROM agent_requests" in normalized:
            return _Rows(self.fixture["requests"])
        if (
            "FROM agent_request_executions" in normalized
            and "count(*)" not in normalized
        ):
            return _Rows(self.fixture["executions"])
        if "decision_code = 'request_approved'" in normalized:
            return _Rows(self.fixture["counts"])
        if "FROM agent_request_decisions" in normalized and "max(id)" not in normalized:
            return _Rows(self.fixture["decisions"])
        if "count(*) AS count" in normalized:
            return _Rows(self.fixture["counts"])
        if "max(id) AS last_decision_id" in normalized:
            return _Rows(self.fixture["last"])
        raise AssertionError(normalized)


class _GovernanceConnection:
    def __init__(self, cursor: _GovernanceCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self, **_kwargs):
        return self._cursor


class _GovernanceRepository:
    def __init__(self, fixture: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        self.cursor = _GovernanceCursor(fixture)

    def _connection_factory(self):
        return _GovernanceConnection(self.cursor)


def _synthetic_governance_contract():
    completed_request, completed_execution, completed_decisions = _governance_fixture(1)
    failed_request, failed_execution, failed_decisions = _governance_fixture(
        2, failed=True
    )
    completed_binding = {
        "request_id": 1,
        "execution_id": completed_execution["id"],
        "reviewer_approval_decision_id": completed_decisions[0]["id"],
        "completion_decision_id": completed_decisions[-1]["id"],
        "request_identity_digest": governance_request_identity_digest(
            completed_request
        ),
        "execution_metadata_digest": governance_execution_metadata_digest(
            completed_execution
        ),
        "reviewer_approval_decision_digest": governance_reviewer_decision_digest(
            completed_decisions[0]
        ),
        "completion_decision_digest": governance_reviewer_decision_digest(
            completed_decisions[-1]
        ),
    }
    failed_binding = {
        "request_id": 2,
        "execution_id": failed_execution["id"],
        "approval_decision_id": failed_decisions[0]["id"],
        "start_decision_id": failed_decisions[1]["id"],
        "failure_decision_id": failed_decisions[-1]["id"],
        "request_identity_digest": governance_request_identity_digest(failed_request),
        "execution_metadata_digest": governance_execution_metadata_digest(
            failed_execution
        ),
        "approval_decision_digest": governance_reviewer_decision_digest(
            failed_decisions[0]
        ),
        "start_decision_digest": governance_reviewer_decision_digest(
            failed_decisions[1]
        ),
        "failure_decision_digest": governance_reviewer_decision_digest(
            failed_decisions[-1]
        ),
        "artifact_paths": [],
        "repository_files_changed": 0,
    }
    fixture = {
        "requests": [completed_request, failed_request],
        "executions": [completed_execution, failed_execution],
        "decisions": [*completed_decisions, *failed_decisions],
        "counts": [{"request_id": 1, "count": 1}, {"request_id": 2, "count": 1}],
        "last": [
            {"request_id": 1, "last_decision_id": completed_decisions[-1]["id"]},
            {"request_id": 2, "last_decision_id": failed_decisions[-1]["id"]},
        ],
    }
    return completed_binding, failed_binding, fixture


def test_governance_digest_equivalence_and_lifecycle_fail_closed(monkeypatch) -> None:
    request, execution, decisions = _governance_fixture(77)
    assert governance_request_identity_digest(
        request
    ) == governance_reference.governance_request_identity_digest(request)
    sanitized_execution = {
        key: value
        for key, value in execution.items()
        if key not in {"status", "completed_at", "artifact_paths"}
    }
    assert governance_execution_metadata_digest(
        sanitized_execution
    ) == governance_reference.governance_execution_metadata_digest(sanitized_execution)
    assert governance_reviewer_decision_digest(
        decisions[0]
    ) == governance_reference.governance_reviewer_decision_digest(decisions[0])
    for forbidden in (
        "result",
        "result_json",
        "execution_result",
        "error",
        "error_json",
    ):
        polluted = dict(sanitized_execution)
        polluted[forbidden] = {"must_not_be_read": True}
        with pytest.raises(ResearchOSValidationError, match="not_sanitized"):
            governance_execution_metadata_digest(polluted)

    completed_binding, failed_binding, fixture = _synthetic_governance_contract()
    monkeypatch.setattr(
        supervisor_module,
        "M4_V2_SUCCESSOR_GOVERNANCE_BINDINGS",
        (completed_binding,),
    )
    monkeypatch.setattr(
        supervisor_module,
        "M4_V2_FAILED_ENGINEERING_PREDECESSOR_BINDING",
        failed_binding,
    )
    repository = _GovernanceRepository(fixture)
    supervisor_module._verify_m4_v2_successor_governance(agent_repository=repository)
    combined_sql = " ".join(repository.cursor.sql).lower()
    assert "result_json" not in combined_sql
    assert "error_json" not in combined_sql
    assert "artifact_paths_json as artifact_paths" in combined_sql

    for mutation in ("duplicate_execution", "later_decision", "artifact_path"):
        broken = copy.deepcopy(fixture)
        if mutation == "duplicate_execution":
            broken["counts"][0]["count"] = 2
        elif mutation == "later_decision":
            broken["last"][0]["last_decision_id"] += 100
        else:
            broken["executions"][0]["artifact_paths"] = ["forbidden.json"]
        with pytest.raises(
            supervisor_module.MainlineSupervisorError, match="lifecycle changed"
        ):
            supervisor_module._verify_m4_v2_successor_governance(
                agent_repository=_GovernanceRepository(broken)
            )

    reused_failed = copy.deepcopy(fixture)
    reused_failed["requests"][1]["status"] = "completed"
    reused_failed["executions"][1]["status"] = "completed"
    with pytest.raises(
        supervisor_module.MainlineSupervisorError,
        match="failed Engineering predecessor",
    ):
        supervisor_module._verify_m4_v2_successor_governance(
            agent_repository=_GovernanceRepository(reused_failed)
        )


def test_governance_constants_and_all_source_contract_seals() -> None:
    bindings = supervisor_module.M4_V2_SUCCESSOR_GOVERNANCE_BINDINGS
    failed = supervisor_module.M4_V2_FAILED_ENGINEERING_PREDECESSOR_BINDING
    assert [item["request_id"] for item in bindings] == [
        478,
        479,
        480,
        481,
        482,
        484,
        485,
        486,
    ]
    assert [item["execution_id"] for item in bindings] == [
        399,
        400,
        402,
        401,
        403,
        405,
        406,
        407,
    ]
    assert len(bindings) == 8
    assert sum(key.endswith("_digest") for item in bindings for key in item) == 32
    assert failed["request_id"] == 483
    assert failed["execution_id"] == 404
    assert failed["artifact_paths"] == []
    assert failed["repository_files_changed"] == 0
    assert sum(key.endswith("_digest") for key in failed) == 5

    assert supervisor_module.M4_V2_HISTORICAL_SOURCE_PIN == (
        "4e787ebc1b13e1a16fe42b80054cb2a01f4c0b6b"
    )
    assert set(supervisor_module.M4_V2_HISTORICAL_SOURCE_IDENTITIES) == {
        "marginal",
        "temporal",
        "joint",
        "global",
    }
    for family, spec in supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS.items():
        legacy = supervisor_module.verify_m4_v2_historical_successor_source_contract(
            root_dir=ROOT_DIR, family=family
        )
        assert (
            legacy["artifact_digest"],
            legacy["source_set_digest"],
        ) == supervisor_module.M4_V2_HISTORICAL_SOURCE_IDENTITIES[family]
        assert len(legacy["source_entries"]) == 7
        if family in {"temporal", "joint"}:
            assert spec["selector"] == f"{family}_v3"
            assert spec["path"].endswith("source-v3.json")
            assert spec["historical_path"].endswith("source-v2.json")
        else:
            # Marginal and Global have no live selector after Request512.  Their
            # checked-out files are irrelevant to this audit-only verifier.
            assert "selector" not in spec


def test_zero_compute_parent_stop_chain_replays_and_global_route() -> None:
    records, completions = _zero_compute_records()
    temporal_completion, joint_completion = completions
    for record, branch_id in zip(records, M4_V2_BRANCH_IDS, strict=True):
        decision = validate_m4_v2_artifact_envelope(record["decision"])
        replay = validate_m4_v2_artifact_envelope(record["replay"])
        assert decision["body"]["branch_id"] == branch_id
        assert replay["body"]["branch_id"] == branch_id
        assert replay["body"]["replay_status"] == "REGISTERED_REPLAY_VERIFIED"
        assert replay["body"]["workload_rerun"] is False
        assert (
            replay["body"]["decision_registration_digest"]
            == replay["parent_digests"][2]
        )
    for decision in (records[1]["decision"], records[2]["decision"]):
        assert (
            decision["body"]["terminal_decision"] == "NOT_EVALUABLE_PARENT_NOT_ACCEPTED"
        )
        assert decision["body"]["scientific_decision"] is None
        assert decision["body"]["evaluation_status"] == "NOT_RUN_PARENT_NOT_ACCEPTED"
    for completion in completions:
        body = completion["body"]
        assert body["historical_outcomes_read"] == 0
        assert body["synthetic_replicate_count"] == 0
        assert body["warmup_alias_position_count"] == 0
        assert body["historical_fold_count"] == 0
        assert body["bootstrap_resample_count"] == 0
        assert body["evidence_created"] is False
        assert body["promotion_gate_opened"] is False
    assert (
        temporal_completion["body"]["registration_count_including_mainline_execution"]
        == 3
    )
    assert (
        joint_completion["body"]["registration_count_including_mainline_execution"] == 3
    )

    route = routing.compile_m4_v2_global_route_decision(
        records,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert route["route"] == "DEEPER_VALIDATION_REQUIRED"
    replay = routing.replay_m4_v2_global_route_decision(
        records,
        route,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["capability_status"] == "REGISTERED_REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["durable_write_count"] == 0


def test_global_router_is_finite_categorical_and_replay_is_pure(monkeypatch) -> None:
    records = _accepted_records()
    route = routing.compile_m4_v2_global_route_decision(
        records,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert route["route"] == "ADAPTIVE_RESEARCH_ELIGIBLE"
    assert route["next_lane"] == "P3_PREDICTIVE_PREREGISTRATION_FREEZE"
    assert route["route"] in routing.GLOBAL_ROUTES
    assert route["decision_replay_coverage"] == "COMPLETE"
    assert route["measurement_global_coverage"] == "FULL"
    assert route["router_conclusive_coverage"] == "FULL"
    assert set(route["decision_projection_rows"][0]) == {
        "branch_id",
        "estimand_digest",
        "decision_path",
        "terminal_decision",
        "scientific_decision",
        "evaluation_status",
        "measurement_health",
        "historical_evidence",
        "accepted_for_downstream_baseline",
        "accepted_model_artifact_digest",
        "baseline_artifact_digest",
        "baseline_source_model_artifact_digest",
        "decision_artifact_digest",
        "decision_producer_execution_id",
        "replay_artifact_digest",
        "replay_registration_digest",
    }

    forbidden_workload_calls = []
    for module, name in (
        (temporal, "build_temporal_warmup_index"),
        (temporal, "build_temporal_composite_view"),
        (joint, "build_q_base_checkpoint_index"),
        (joint, "build_joint_z_checkpoint_index"),
        (joint, "build_joint_target_prediction_index"),
    ):
        monkeypatch.setattr(
            module,
            name,
            lambda *_args, _name=name, **_kwargs: forbidden_workload_calls.append(
                _name
            ),
        )
    replay = routing.replay_m4_v2_global_route_decision(
        records,
        route,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert forbidden_workload_calls == []
    assert replay == {
        "status": "REPLAY_VERIFIED",
        "outer_status": "REPLAY_VERIFIED",
        "capability_status": "REGISTERED_REPLAY_VERIFIED",
        "same_route_decision_identity": True,
        "same_registered_content": True,
        "route_artifact_digest": route["artifact_digest"],
        "source_integrity_verified": True,
        "workload_rerun": False,
        "raw_history_read": False,
        "numerical_result_payload_read": False,
        "durable_write_count": 0,
        "new_fact_count": 0,
        "durable_state_changed": False,
    }
    source = inspect.getsource(routing.compile_m4_v2_global_route_decision)
    assert "repository" not in source.lower()
    assert "fold" not in source.lower()


def test_global_router_repair_and_partial_positive_never_adaptive() -> None:
    repair_records, _ = _zero_compute_records(
        marginal_evidence="INCONCLUSIVE", health="REPAIR"
    )
    repair = routing.compile_m4_v2_global_route_decision(
        repair_records,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert repair["route"] == "MEASUREMENT_REPAIR_REQUIRED"
    assert repair["route"] != "ADAPTIVE_RESEARCH_ELIGIBLE"

    partial = routing.compile_m4_v2_global_route_decision(
        _partial_positive_records(),
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert partial["positive_branches"] == ["MARGINAL_STATIC"]
    assert partial["measurement_global_coverage"] == "PARTIAL"
    assert partial["router_conclusive_coverage"] == "PARTIAL"
    assert partial["route"] == "DEEPER_VALIDATION_REQUIRED"
    assert partial["route"] != "ADAPTIVE_RESEARCH_ELIGIBLE"


def test_resolver_global_route_and_four_and_p3_barrier() -> None:
    payload = _successor_payload()
    manifest = ControlPlaneManifest.from_dict(payload)
    successor_task_keys = {
        marginal_builder.RECOVERY_TASK_KEY,
        *(M4_V2_SUCCESSOR_TASKS.values()),
    } - {marginal_builder.DECISION_TASK_KEY}
    assert marginal_builder.RECOVERY_TASK_KEY in {
        task.task_key for task in manifest.tasks
    }
    global_task = _task(payload, global_builder.GLOBAL_TASK)
    placeholder = _task(payload, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY)
    predictive_p3 = _task(payload, PREDICTIVE_P3_TASK_KEY)
    assert global_task["requested_capability"] == routing.GLOBAL_ROUTE_CAPABILITY
    assert _dependency_tuples(global_task) == (
        ("artifact", global_builder.SOURCE_FACT, "available"),
        *(("artifact", fact, "available") for fact in M4_V2_SUCCESSOR_REPLAY_FACTS),
    )
    assert placeholder["requested_capability"] is None
    assert placeholder["metric_contract"]["runner"] is None
    assert placeholder["metric_contract"]["execution_authorized"] is False
    assert placeholder["completion_classification"] == "INTEGRATION_PENDING"
    assert _dependency_tuples(placeholder) == (
        ("task", global_builder.GLOBAL_TASK, "completed"),
        ("artifact", routing.ADAPTIVE_RESEARCH_ELIGIBILITY_FACT, "available"),
    )
    assert _dependency_tuples(predictive_p3) == (
        *_dependency_tuples(placeholder),
        ("task", M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY, "completed"),
        ("artifact", M4_P3_PREDICTIVE_PREREGISTRATION_FACT, "available"),
    )

    for fact in M4_V2_SUCCESSOR_REPLAY_FACTS[:-1]:
        _add_facts(payload, fact)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, global_builder.GLOBAL_TASK).status
        is TaskStatus.DEPENDENCY_WAIT
    )

    _add_facts(payload, M4_V2_SUCCESSOR_REPLAY_FACTS[-1])
    for task_key in successor_task_keys - {global_builder.GLOBAL_TASK}:
        _set_task_completed(payload, task_key)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    successor_ready = [
        item.task_key
        for item in ResearchOSControlPlane().resolve(manifest).ready_queue
        if item.task_key in successor_task_keys
    ]
    assert successor_ready == [global_builder.GLOBAL_TASK]

    _set_task_completed(payload, global_builder.GLOBAL_TASK)
    _add_facts(payload, routing.ADAPTIVE_RESEARCH_ELIGIBILITY_FACT)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY).status
        is TaskStatus.READY
    )
    assert (
        _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )

    _set_task_completed(payload, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )
    assert M4_P3_PREDICTIVE_PREREGISTRATION_FACT not in manifest.facts.artifacts

    _add_facts(payload, M4_P3_PREDICTIVE_PREREGISTRATION_FACT)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status is TaskStatus.READY
    successor_capabilities = {
        task["requested_capability"]
        for task in payload["tasks"]
        if task["task_key"] in successor_task_keys
    }
    assert (
        _task(payload, PREDICTIVE_P3_TASK_KEY)["requested_capability"]
        not in successor_capabilities
    )


def test_p4_requires_completed_p3_and_explicit_pass() -> None:
    payload = _successor_payload()
    p4 = _task(payload, PREDICTIVE_P4_TASK_KEY)
    assert _dependency_tuples(p4) == (
        ("task", PREDICTIVE_P3_TASK_KEY, "completed"),
        ("artifact", PREDICTIVE_P3_PASS_TO_P4_FACT, "available"),
    )
    _set_task_completed(payload, global_builder.GLOBAL_TASK)
    _set_task_completed(payload, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY)
    _add_facts(
        payload,
        routing.ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
        M4_P3_PREDICTIVE_PREREGISTRATION_FACT,
    )
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status is TaskStatus.READY
    assert (
        _resolution(manifest, PREDICTIVE_P4_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )
    _set_task_completed(payload, PREDICTIVE_P3_TASK_KEY)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, PREDICTIVE_P4_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )
    _add_facts(payload, PREDICTIVE_P3_PASS_TO_P4_FACT)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert _resolution(manifest, PREDICTIVE_P4_TASK_KEY).status is TaskStatus.READY


def test_source_contracts_exact_closure_and_digest_drift_fail_closed(
    tmp_path: Path,
) -> None:
    specs = supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS
    legacy_source_sets: dict[str, tuple[str, ...]] = {}
    for family in ("marginal", "temporal", "joint", "global"):
        contract = supervisor_module.verify_m4_v2_historical_successor_source_contract(
            root_dir=ROOT_DIR, family=family
        )
        entries = tuple(item["path"] for item in contract["source_entries"])
        assert len(entries) == len(set(entries)) == 7
        legacy_source_sets[family] = entries
        for item in contract["source_entries"]:
            historical_bytes = supervisor_module._m4_v2_raw_git_blob(
                root_dir=ROOT_DIR,
                commit=supervisor_module.M4_V2_HISTORICAL_SOURCE_PIN,
                path=item["path"],
            )
            assert item["sha256"] == hashlib.sha256(historical_bytes).hexdigest()

    active_source_sets: dict[str, tuple[str, ...]] = {}
    for family in ("marginal", "global"):
        contract = supervisor_module._load_m4_v2_successor_source_contract(
            root_dir=ROOT_DIR, family=family
        )
        entries = tuple(item["path"] for item in contract["source_entries"])
        assert len(entries) == len(set(entries)) == 7
        assert contract["artifact_digest"] == json.loads(
            SOURCE_PATHS[0 if family == "marginal" else 3].read_text(encoding="utf-8")
        )["artifact_digest"]
        active_source_sets[family] = entries
    expected_arrays = {
        "temporal": "c3aa7e4fbb5a60393e68582ebf9b47d572892b8c2a8494db8065b8a604ab1898",
        "joint": "b9d51e1feb75e656708e410c9f719d839fedc3ed5c6dc2eae9929be8bfdcb60d",
    }
    for family in ("temporal", "joint"):
        selector = specs[family]["selector"]
        contract = supervisor_module.load_m4_v2_active_successor_source_contract(
            root_dir=ROOT_DIR, selector=selector
        )
        entries = tuple(item["path"] for item in contract["source_entries"])
        assert entries == tuple(specs[family]["entries"])
        assert len(entries) == len(set(entries)) == 12
        assert contract["schema_version"].endswith("source-contract.v3")
        assert contract["source_path_array_contract_version"] == 4
        assert contract["source_path_array_digest"] == expected_arrays[family]
        assert contract["accepted_support_input_schema"] == (
            "dehps-m4-v2-accepted-support-input.v3"
        )
        assert all(
            item["sha256"]
            == hashlib.sha256((ROOT_DIR / item["path"]).read_bytes()).hexdigest()
            for item in contract["source_entries"]
        )
        active_source_sets[family] = entries

    for rejected_selector in (
        "marginal",
        "global",
        "temporal",
        "joint",
        "temporal_v2",
        "joint_v2",
    ):
        with pytest.raises(
            supervisor_module.MainlineSupervisorError,
            match="selector is not authorized",
        ):
            supervisor_module.load_m4_v2_active_successor_source_contract(
                root_dir=ROOT_DIR, selector=rejected_selector
            )

    assert "branch_decision" not in {
        node.module
        for module in (temporal, joint, routing)
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert M4V2BranchDecisionArtifact.__module__ == "dehps.research_os.models"

    family = "temporal"
    spec = specs[family]
    for entry in supervisor_module.load_m4_v2_active_successor_source_contract(
        root_dir=ROOT_DIR, selector=spec["selector"]
    )["source_entries"]:
        target = tmp_path / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / entry["path"], target)
    contract_target = tmp_path / spec["path"]
    contract_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT_DIR / spec["path"], contract_target)
    first_source = tmp_path / spec["entries"][0]
    first_source.write_bytes(first_source.read_bytes() + b"\n# digest drift\n")
    with pytest.raises(
        supervisor_module.MainlineSupervisorError, match="source bytes changed"
    ):
        supervisor_module.load_m4_v2_active_successor_source_contract(
            root_dir=tmp_path, selector=spec["selector"]
        )

    original_raw_git_blob = supervisor_module._m4_v2_raw_git_blob

    def tampered_historical_blob(*, root_dir: Path, commit: str, path: str) -> bytes:
        content = original_raw_git_blob(root_dir=root_dir, commit=commit, path=path)
        if path == legacy_source_sets["joint"][0]:
            return content + b"\n# historical tamper\n"
        return content

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            supervisor_module, "_m4_v2_raw_git_blob", tampered_historical_blob
        )
        with pytest.raises(
            supervisor_module.MainlineSupervisorError,
            match="historical source bytes changed",
        ):
            supervisor_module.verify_m4_v2_historical_successor_source_contract(
                root_dir=ROOT_DIR, family="joint"
            )


def test_successor_v2_estimator_identity_rejects_predecessor_v1() -> None:
    payload = _successor_payload()
    temporal_tasks = [
        item
        for item in payload["tasks"]
        if item["task_key"].startswith("m4-v2-temporal-marginal-increment")
    ]
    joint_tasks = [
        item
        for item in payload["tasks"]
        if item["task_key"].startswith("m4-v2-joint-residual-increment")
    ]
    assert temporal_tasks and joint_tasks
    temporal_source = json.loads(SOURCE_PATHS[1].read_text(encoding="utf-8"))[
        "artifact_digest"
    ]
    joint_source = json.loads(SOURCE_PATHS[2].read_text(encoding="utf-8"))[
        "artifact_digest"
    ]
    assert all(item["input_artifact_digests"] == [temporal_source] for item in temporal_tasks)
    assert all(item["input_artifact_digests"] == [joint_source] for item in joint_tasks)
    assert all(
        item["metric_contract"]["estimator_id"] == temporal.TEMPORAL_MODEL_ID
        for item in temporal_tasks
    )
    assert all(
        item["metric_contract"]["estimator_id"] == joint.JOINT_ESTIMATOR_ID
        for item in joint_tasks
    )
    assert joint.REQUEST481_PREDECESSOR_ESTIMATOR_ID != joint.JOINT_ESTIMATOR_ID
    assert (
        temporal.REQUEST481_PREDECESSOR_JOINT_ESTIMATOR_ID
        != temporal.SUCCESSOR_JOINT_ESTIMATOR_ID
    )
    assert (
        supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["temporal"]["selector"]
        == "temporal_v3"
    )
    assert (
        supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["joint"]["selector"]
        == "joint_v3"
    )
    assert supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["temporal"]["path"].endswith(
        "source-v3.json"
    )
    assert supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["joint"]["path"].endswith(
        "source-v3.json"
    )


def _warmup_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rule = temporal.build_transition_local_warmup_rule()
    rows = []
    for ordinal in range(temporal.WARMUP_START, temporal.WARMUP_END + 1):
        checkpoint = temporal.build_strict_prior_marginal_checkpoint(
            transition_ordinal=ordinal,
            issue=f"issue-{ordinal}",
            prefix_last_issue=f"issue-{ordinal - 1}",
            prefix_outcome_chain_digest=_digest(f"prefix-{ordinal}"),
            q_m_marginal_content_digest=_digest(f"qm-marginal-{ordinal}"),
            q_m_full_distribution_content_digest=_digest(f"qm-full-{ordinal}"),
        )
        rows.append(temporal.build_temporal_warmup_row(checkpoint))
    return rule, rows


def test_fixed_null_warmup_exact_alias_and_falsifiers() -> None:
    rule, rows = _warmup_rows()
    index = temporal.build_temporal_warmup_index(rows, rule_digest=rule["rule_digest"])
    assert rule["transition_range"] == [2, 900]
    assert rule["transition_count"] == 899
    assert rule["theta_float_hex"] == "0x0.0p+0"
    assert rule["theta_ieee754_binary64_be_hex"] == "0000000000000000"
    assert rule["negative_zero_allowed"] is False
    assert rule["temporal_theta_fit_invoked"] is False
    assert rule["temporal_theta_root_existence_test_invoked"] is False
    assert rule["regularization"] is None
    assert rule["fallback"] is None
    assert index["row_count"] == 899
    assert [item["transition_ordinal"] for item in rows] == list(range(2, 901))
    assert all(
        item["q_t_marginal_content_digest"] == item["q_m_marginal_content_digest"]
        for item in rows
    )
    assert all(
        item["q_t_full_distribution_content_digest"]
        == item["q_m_full_distribution_content_digest"]
        for item in rows
    )
    assert all(item["temporal_theta_fit_invoked"] is False for item in rows)

    for field, changed in (
        ("theta_float_hex", "-0x0.0p+0"),
        ("theta_float_hex", "0x1.0000000000000p-1"),
        ("temporal_theta_fit_invoked", True),
        ("q_t_full_distribution_content_digest", _digest("reconstructed-q-t")),
    ):
        tampered = copy.deepcopy(rows[0])
        tampered[field] = changed
        with pytest.raises(temporal.TemporalMarginalIncrementContractError):
            temporal.validate_temporal_warmup_row(tampered)
    with pytest.raises(
        temporal.TemporalMarginalIncrementContractError, match="coverage_or_order"
    ):
        temporal.build_temporal_warmup_index(rows[:-1], rule_digest=rule["rule_digest"])
    duplicated = [*rows[:-1], rows[-2]]
    with pytest.raises(
        temporal.TemporalMarginalIncrementContractError, match="coverage_or_order"
    ):
        temporal.build_temporal_warmup_index(
            duplicated, rule_digest=rule["rule_digest"]
        )

    same_prefix = dict(rows[10])
    same_prefix["non_identity_suffix_provenance"] = "changed"
    temporal.assert_temporal_suffix_noninterference(rows[10], same_prefix)
    changed_prefix = dict(rows[10])
    changed_prefix["q_m_full_distribution_content_digest"] = _digest("suffix-leak")
    with pytest.raises(temporal.TemporalMarginalIncrementContractError, match="suffix"):
        temporal.assert_temporal_suffix_noninterference(rows[10], changed_prefix)
    assert (
        temporal.temporal_synthetic_warmup_position(
            cell_index=0, replicate_index=0, transition_ordinal=2
        )
        == 0
    )
    assert (
        temporal.temporal_synthetic_warmup_position(
            cell_index=13, replicate_index=511, transition_ordinal=900
        )
        == 6_444_031
    )


def test_temporal_composite_and_joint_chronology_contracts() -> None:
    view = temporal.build_temporal_composite_view(
        warmup_index_digest=_digest("warmup-index"),
        accepted_temporal_evaluation_index_digest=_digest("accepted-index"),
    )
    assert view["transition_range"] == [2, 3481]
    assert view["row_count"] == 3480
    assert temporal.temporal_checkpoint_plan(900).theta_fit_invoked is False
    assert temporal.temporal_checkpoint_plan(901).prefix_last_ordinal == 900
    assert temporal.temporal_checkpoint_plan(901).theta_fit_invoked is True
    assert temporal.temporal_checkpoint_plan(902).prefix_last_ordinal == 901
    assert joint.joint_checkpoint_plan(901).eta_training_range == (2, 900)
    assert joint.joint_checkpoint_plan(901).eta_training_count == 899
    assert joint.joint_checkpoint_plan(902).eta_training_range == (2, 901)
    assert joint.joint_checkpoint_plan(902).eta_training_count == 900
    assert joint.joint_checkpoint_plan(902).target_z_may_be_reconstructed is False


def test_synthetic_cartesian_grid_seed_and_count_invariance() -> None:
    expected_counts = {
        "cell_count": 14,
        "replicates_per_cell": 512,
        "synthetic_replicate_count": 7168,
        "synthetic_generated_issue_count": 15_920_128,
        "outer_evaluation_issue_count": 9_468_928,
        "bootstrap_resample_count": 14_651_392,
        "historical_fold_count": 2581,
        "historical_child_count": 16_000,
        "warmup_transition_count_per_replicate": 899,
        "warmup_alias_position_count": 6_444_032,
    }
    assert dict(temporal.PLANNED_COUNTS) == expected_counts
    assert dict(joint.PLANNED_COUNTS) == expected_counts
    assert temporal.SYNTHETIC_WARMUP_RNG_CALL_COUNT == 0
    assert joint.SYNTHETIC_WARMUP_RNG_CALL_COUNT == 0
    assert temporal.SYNTHETIC_BOOTSTRAP_SEED_MATERIAL_CHANGED_BY_WARMUP is False
    assert joint.SYNTHETIC_BOOTSTRAP_SEED_MATERIAL_CHANGED_BY_WARMUP is False
    assert temporal.SYNTHETIC_WARMUP_COMPUTED_PER_BOOTSTRAP_CHILD is False
    assert joint.SYNTHETIC_WARMUP_COMPUTED_PER_BOOTSTRAP_CHILD is False

    health = _digest("health-contract")
    seed = _digest("seed-contract")
    temporal_coordinates = [
        temporal.build_temporal_synthetic_sequence_coordinate(
            health_contract_digest=health,
            seed_contract_digest=seed,
            cell_index=cell,
            replicate_index=replicate,
        )
        for cell in range(14)
        for replicate in range(512)
    ]
    joint_coordinates = [
        joint.build_joint_synthetic_sequence_coordinate(
            health_contract_digest=health,
            seed_contract_digest=seed,
            cell_index=cell,
            replicate_index=replicate,
        )
        for cell in range(14)
        for replicate in range(512)
    ]
    assert len(temporal_coordinates) == len(joint_coordinates) == 7168
    assert len({item["coordinate_digest"] for item in temporal_coordinates}) == 7168
    assert len({item["coordinate_digest"] for item in joint_coordinates}) == 7168
    assert {item["coordinate_digest"] for item in temporal_coordinates}.isdisjoint(
        item["coordinate_digest"] for item in joint_coordinates
    )
    assert all(
        item["seed_contract_digest"] == seed
        for item in temporal_coordinates + joint_coordinates
    )
    assert all(
        item["sequence_seed_full_sha256"] != seed
        for item in temporal_coordinates + joint_coordinates
    )
    tampered = copy.deepcopy(temporal_coordinates[0])
    tampered["sequence_seed_full_sha256"] = _digest("seed-drift")
    with pytest.raises(
        temporal.TemporalMarginalIncrementContractError, match="seed_or_cell"
    ):
        temporal.validate_temporal_synthetic_sequence_coordinate(tampered)


def test_all_17_artifact_types_nested_lineage_paths_and_cardinalities() -> None:
    assert len(M4_V2_ARTIFACT_TYPE_REGISTRY) == 17
    assert set(M4_V2_ARTIFACT_TYPE_REGISTRY) == EXPECTED_ARTIFACT_TYPES
    assert len(M4_V2_NESTED_SCHEMA_REGISTRY) == 46
    assert all(spec.body_fields for spec in M4_V2_ARTIFACT_TYPE_REGISTRY.values())
    assert all(
        len(spec.body_fields) == len(set(spec.body_fields))
        for spec in M4_V2_ARTIFACT_TYPE_REGISTRY.values()
    )

    records, completions = _zero_compute_records()
    for record in records:
        for artifact_name in ("decision", "replay"):
            envelope = record[artifact_name]
            validate_m4_v2_artifact_envelope(envelope)
            missing = copy.deepcopy(envelope)
            missing.pop("parent_digests")
            with pytest.raises(ResearchOSValidationError):
                validate_m4_v2_artifact_envelope(missing)
            extra = copy.deepcopy(envelope)
            extra["sidecar"] = {}
            with pytest.raises(ResearchOSValidationError):
                validate_m4_v2_artifact_envelope(extra)
    eighteenth = copy.deepcopy(records[0]["decision"])
    eighteenth["artifact_type"] = "M4V2ForbiddenEighteenthArtifact"
    with pytest.raises(ResearchOSValidationError, match="unknown"):
        validate_m4_v2_artifact_envelope(eighteenth)

    assert temporal.temporal_registration_plan(
        "PARENT_NOT_ACCEPTED"
    ).artifact_types_in_registration_order == (
        "M4V2BranchDecisionArtifact",
        "M4V2TemporalMarginalIncrementProducerCompletionArtifact",
        "research_os_mainline_execution",
    )
    assert joint.joint_registration_plan(
        "PARENT_NOT_ACCEPTED"
    ).artifact_types_in_registration_order == (
        "M4V2BranchDecisionArtifact",
        "M4V2JointResidualProducerCompletionArtifact",
        "research_os_mainline_execution",
    )
    assert (
        temporal.temporal_registration_plan(
            "EVALUATED_COMPLETE"
        ).registration_count_including_mainline_execution
        == 6
    )
    assert (
        joint.joint_registration_plan(
            "EVALUATED_COMPLETE"
        ).registration_count_including_mainline_execution
        == 7
    )
    for completion in completions:
        assert (
            completion["artifact_digest"]
            not in completion["body"]["registered_artifact_digests_in_order"]
        )

    q_digest = _digest("q")
    certificate = joint.build_q_base_reconstruction_certificate(
        transition_ordinal=2,
        temporal_support_row_digest=_digest("temporal-row"),
        q_t_full_distribution_content_digest=q_digest,
        q_base_full_distribution_content_digest=q_digest,
        max_probability_difference_float_hex="0x0.0p+0",
        max_marginal_difference_float_hex="0x0.0p+0",
        normalization_residual_float_hex="0x0.0p+0",
    )
    checkpoint = joint.build_q_base_checkpoint(
        transition_ordinal=2,
        issue="issue-2",
        temporal_support_row_digest=_digest("temporal-row"),
        temporal_composite_view_digest=_digest("temporal-view"),
        q_t_marginal_content_digest=_digest("q-marginal"),
        q_t_full_distribution_content_digest=q_digest,
        baseline_contract_digest=_digest("baseline-contract"),
        reconstruction_certificate=certificate,
    )
    assert checkpoint["q_base_full_distribution_content_digest"] == q_digest
    drift = copy.deepcopy(checkpoint)
    drift["q_base_full_distribution_content_digest"] = _digest("qbase-drift")
    with pytest.raises(joint.JointResidualIncrementContractError, match="alias"):
        joint.validate_q_base_checkpoint(drift)
    coordinate = joint.build_certificate_coordinate_identity(
        scope="HISTORICAL_Z",
        source_contract_digest=_digest("joint-source"),
        preregistration_artifact_digest=_digest("joint-prereg"),
        producer_execution_id=_digest("joint-producer"),
        transition_ordinal=2,
        issue_or_sequence_coordinate_digest="issue-2",
        support_kind="WARMUP_NULL_ALIAS",
    )
    validate_m4_v2_nested_schema("certificate_coordinate_identity", coordinate)
    coordinate_drift = copy.deepcopy(coordinate)
    coordinate_drift["transition_ordinal"] = 3
    with pytest.raises(joint.JointResidualIncrementContractError):
        joint.validate_certificate_coordinate_identity(coordinate_drift)

    execution_id = _digest("global-execution")
    artifact_digest = _digest("global-route-artifact")
    expected_path = (
        f"runtime/research-os/mainline/tasks/{routing.GLOBAL_ROUTE_TASK_KEY}/"
        f"{execution_id}/artifacts/global-routing-decision/{artifact_digest}/decision.json"
    )
    assert (
        routing.m4_v2_global_route_artifact_path(
            execution_id=execution_id, artifact_digest=artifact_digest
        )
        == expected_path
    )


def test_holm_lineage_and_formal_one_rules_fail_before_workload() -> None:
    exact = temporal.validate_accepted_parent_raw_p_lineage(
        parent_branch_id="MARGINAL_STATIC",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        accepted_for_downstream_baseline=True,
        historical_artifact_digest=temporal.MARGINAL_RAW_P_ARTIFACT_DIGEST,
        historical_registration_digest=temporal.MARGINAL_RAW_P_REGISTRATION_DIGEST,
        producer_execution_id=_digest("marginal-producer"),
        replay_status="REGISTERED_REPLAY_VERIFIED",
        raw_primary_p_value=0.125,
    )
    assert exact == 0.125
    for changed in (
        {"historical_artifact_digest": _digest("missing-historical")},
        {"historical_registration_digest": _digest("missing-registration")},
        {"replay_status": "REPLAY_VERIFIED"},
        {"accepted_for_downstream_baseline": False},
    ):
        arguments = {
            "parent_branch_id": "MARGINAL_STATIC",
            "terminal_decision": "BRANCH_INFORMATION_ACCEPTED",
            "accepted_for_downstream_baseline": True,
            "historical_artifact_digest": temporal.MARGINAL_RAW_P_ARTIFACT_DIGEST,
            "historical_registration_digest": temporal.MARGINAL_RAW_P_REGISTRATION_DIGEST,
            "producer_execution_id": _digest("marginal-producer"),
            "replay_status": "REGISTERED_REPLAY_VERIFIED",
            "raw_primary_p_value": 0.125,
            **changed,
        }
        with pytest.raises(
            temporal.TemporalMarginalIncrementContractError, match="lineage"
        ):
            temporal.validate_accepted_parent_raw_p_lineage(**arguments)
    assert (
        temporal.validate_temporal_holm_family(
            {
                "MARGINAL_STATIC": 0.125,
                "TEMPORAL_MARGINAL_INCREMENT": 0.25,
                "JOINT_RESIDUAL_INCREMENT": 1.0,
            },
            marginal_raw_p_value=0.125,
            temporal_raw_p_value=0.25,
        )["JOINT_RESIDUAL_INCREMENT"]
        == 1.0
    )
    assert joint.formal_holm_one_allowed(
        branch_id="JOINT_RESIDUAL_INCREMENT",
        terminal_decision=None,
        replay_status=None,
        temporal_is_current_evaluated_branch=True,
        joint_has_formally_not_run=True,
    )
    for terminal in (
        "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
        "MEASUREMENT_REPAIR_REQUIRED",
        "INVALID_EXECUTION",
    ):
        assert joint.formal_holm_one_allowed(
            branch_id="TEMPORAL_MARGINAL_INCREMENT",
            terminal_decision=terminal,
            replay_status="REGISTERED_REPLAY_VERIFIED",
        )
    assert not joint.formal_holm_one_allowed(
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        terminal_decision="NO_DETECTABLE_INFORMATION",
        replay_status="REGISTERED_REPLAY_VERIFIED",
    )
    assert not joint.formal_holm_one_allowed(
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        terminal_decision="INVALID_EXECUTION",
        replay_status=None,
    )


def test_supervisor_global_replay_is_zero_write_and_preserves_all_identities(
    monkeypatch,
) -> None:
    payload = _successor_payload()
    manifest = ControlPlaneManifest.from_dict(payload)
    before_manifest = m4_v2_canonical_json(manifest.to_dict(include_digest=True))
    before_snapshot = ResearchOSControlPlane().resolve(manifest)
    before_ready = m4_v2_canonical_json(jsonable(before_snapshot.ready_queue))
    records = _accepted_records()
    route = routing.compile_m4_v2_global_route_decision(
        records,
        source_contract_digest=_digest("global-source"),
        task_digest=next(
            task
            for task in manifest.tasks
            if task.task_key == routing.GLOBAL_ROUTE_TASK_KEY
        ).artifact_digest,
    )

    class ReadOnlyRepository:
        def __init__(self):
            self.loads = 0
            self.writes: list[str] = []
            self.control_plane = ResearchOSControlPlane()

        def load_manifest(self, *, control_plane_key: str):
            assert control_plane_key == CONTROL_PLANE_KEY
            self.loads += 1
            return manifest

        def __getattr__(self, name: str):
            if any(
                token in name
                for token in (
                    "record",
                    "import",
                    "write",
                    "register",
                    "update",
                    "append",
                )
            ):

                def forbidden(*_args, **_kwargs):
                    self.writes.append(name)
                    raise AssertionError(f"durable write attempted: {name}")

                return forbidden
            raise AttributeError(name)

    repository = ReadOnlyRepository()
    execution_id = _digest("global-execution")
    execution_artifact = {
        "execution_id": execution_id,
        "artifact_digest": _digest("global-execution-artifact"),
    }
    registrations = [
        {"artifact_type": routing.GLOBAL_ROUTE_ARTIFACT_TYPE},
        {"artifact_type": "research_os_mainline_execution"},
    ]
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_kwargs: ({}, execution_artifact, registrations),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_m4_v2_successor_source_contract",
        lambda **_kwargs: {"artifact_digest": _digest("global-source")},
    )
    monkeypatch.setattr(
        supervisor_module.M4V2SuccessorCapability,
        "_source",
        lambda _self, _family, _task: {"artifact_digest": _digest("global-source")},
    )
    by_decision_task = {
        marginal_builder.RECOVERY_TASK_KEY: records[0],
        temporal.TEMPORAL_PRODUCER_TASK_KEY: records[1],
        joint.JOINT_PRODUCER_TASK_KEY: records[2],
    }
    monkeypatch.setattr(
        supervisor_module.M4V2SuccessorCapability,
        "_branch_record",
        lambda _self, **kwargs: by_decision_task[kwargs["decision_task_key"]],
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **_kwargs: route,
    )
    supervisor = object.__new__(supervisor_module.ResearchEvidenceSupervisor)
    supervisor.repository = repository
    supervisor.root_dir = ROOT_DIR
    supervisor.control_plane_key = CONTROL_PLANE_KEY
    status_projection_calls: list[str] = []
    monkeypatch.setattr(
        supervisor,
        "_build_lane_status",
        lambda current_manifest, **kwargs: (
            status_projection_calls.append(current_manifest.artifact_digest)
            or {
                "manifest_digest": current_manifest.artifact_digest,
                "snapshot_digest": kwargs["snapshot"].snapshot_digest,
                "ready_queue": jsonable(kwargs["snapshot"].ready_queue),
            }
        ),
    )
    monkeypatch.setattr(
        supervisor,
        "_write_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("state write")),
    )
    monkeypatch.setattr(
        supervisor,
        "_write_lane_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("lane write")),
    )
    replay = supervisor.replay(task_key=routing.GLOBAL_ROUTE_TASK_KEY)
    assert replay["status"] == "REPLAY_VERIFIED"
    assert (
        replay["capability_replay"]["capability_status"] == "REGISTERED_REPLAY_VERIFIED"
    )
    assert replay["capability_replay"]["workload_rerun"] is False
    assert replay["durable_state_changed"] is False
    assert repository.writes == []
    assert status_projection_calls == [manifest.artifact_digest]
    assert (
        m4_v2_canonical_json(manifest.to_dict(include_digest=True)) == before_manifest
    )
    after_snapshot = ResearchOSControlPlane().resolve(manifest)
    assert after_snapshot.snapshot_digest == before_snapshot.snapshot_digest
    assert m4_v2_canonical_json(jsonable(after_snapshot.ready_queue)) == before_ready


class _RegistrationCursor:
    def __init__(self, stored: Mapping[str, Any] | None) -> None:
        self.stored = None if stored is None else copy.deepcopy(dict(stored))
        self._last = ""

    def execute(self, sql: str, _params: Any):
        self._last = " ".join(sql.split())
        return self

    def fetchone(self):
        if "SELECT registration_json" in self._last:
            return None if self.stored is None else {"registration_json": self.stored}
        raise AssertionError(self._last)


def test_atomic_publication_crash_reconciliation_and_conflicts(
    tmp_path: Path, monkeypatch
) -> None:
    staged = tmp_path / ".staging" / "00.json"
    content = b'{"frozen":true}\n'
    fsync_calls: list[int] = []
    real_fsync = os.fsync

    def observed_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(supervisor_module.os, "fsync", observed_fsync)
    supervisor_module._atomic_write_staged_file(staged, content)
    assert staged.read_bytes() == content
    assert len(fsync_calls) >= 2
    with pytest.raises(FileExistsError):
        supervisor_module._atomic_write_staged_file(staged, content)

    destination = tmp_path / "canonical" / "artifact.json"
    ownership = supervisor_module._atomic_publish_noreplace(staged, destination)
    assert ownership[2] is True
    assert not staged.exists()
    assert destination.read_bytes() == content

    identical_stage = tmp_path / ".staging" / "01.json"
    supervisor_module._atomic_write_staged_file(identical_stage, content)
    preexisting = supervisor_module._atomic_publish_noreplace(
        identical_stage, destination
    )
    assert preexisting[2] is False
    assert identical_stage.exists()
    mismatch_stage = tmp_path / ".staging" / "02.json"
    supervisor_module._atomic_write_staged_file(mismatch_stage, b"different\n")
    with pytest.raises(supervisor_module.MainlineSupervisorError, match="collision"):
        supervisor_module._atomic_publish_noreplace(mismatch_stage, destination)
    assert destination.read_bytes() == content

    supervisor_module.ResearchEvidenceSupervisor._cleanup_owned_atomic_paths(
        {destination: ownership}
    )
    assert not destination.exists()
    preserved = tmp_path / "canonical" / "preexisting.json"
    preserved.parent.mkdir(parents=True, exist_ok=True)
    preserved.write_bytes(content)
    stat = preserved.stat()
    supervisor_module.ResearchEvidenceSupervisor._cleanup_owned_atomic_paths(
        {preserved: (stat.st_dev, stat.st_ino, False)}
    )
    assert preserved.exists()

    registration = MainlineArtifactRegistration(
        execution_id=_digest("execution"),
        control_plane_key=CONTROL_PLANE_KEY,
        task_key="task",
        task_digest=_digest("task"),
        artifact_digest=_digest("artifact"),
        artifact_type="artifact",
        schema_version="v1",
        artifact_path="runtime/research-os/mainline/tasks/task/artifact.json",
        parent_digests=(_digest("parent"),),
        git_commit=GIT_COMMIT,
    )
    exact = jsonable(registration)
    supervisor_module._atomic_insert_registration(
        _RegistrationCursor(exact), registration
    )
    mismatch = dict(exact)
    mismatch["artifact_path"] = "mismatch"
    with pytest.raises(
        supervisor_module.MainlineSupervisorError, match="not idempotent"
    ):
        supervisor_module._atomic_insert_registration(
            _RegistrationCursor(mismatch), registration
        )

    class ReconciliationRepository:
        def __init__(
            self,
            *,
            head_digest: str,
            registrations: Sequence[Mapping[str, Any]],
            completed_event_count: int,
        ) -> None:
            self.head_digest = head_digest
            self.registrations = list(registrations)
            self.completed_event_count = completed_event_count

        def load_manifest(self, *, control_plane_key: str):
            assert control_plane_key == CONTROL_PLANE_KEY
            return SimpleNamespace(artifact_digest=self.head_digest)

        def list_mainline_execution_events(self, **_kwargs):
            return [
                {"event_type": "completed"} for _ in range(self.completed_event_count)
            ]

        def list_mainline_artifacts(self, **_kwargs):
            return copy.deepcopy(self.registrations)

    expected_row = {
        "registration_digest": registration.registration_digest,
        **jsonable(registration),
    }
    head = _digest("head")
    complete = _digest("complete")
    task = SimpleNamespace(task_key="task")

    def reconcile(repository: Any) -> str:
        instance = object.__new__(supervisor_module.ResearchEvidenceSupervisor)
        instance.repository = repository
        instance.root_dir = ROOT_DIR
        instance.control_plane_key = CONTROL_PLANE_KEY
        return instance._reconcile_atomic_completion(
            task=task,
            execution_id=registration.execution_id,
            expected_head_manifest_digest=head,
            completed_manifest_digest=complete,
            expected_registrations=(registration,),
        )

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_kwargs: ({}, {}, []),
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[expected_row],
                completed_event_count=1,
            )
        )
        == "COMMITTED"
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=head,
                registrations=[],
                completed_event_count=0,
            )
        )
        == "ABSENT"
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[expected_row],
                completed_event_count=0,
            )
        )
        == "INCIDENT"
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[],
                completed_event_count=1,
            )
        )
        == "INCIDENT"
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_kwargs: (_ for _ in ()).throw(
            supervisor_module.MainlineSupervisorError("registered file missing")
        ),
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[expected_row],
                completed_event_count=1,
            )
        )
        == "INCIDENT"
    )

    source = inspect.getsource(
        supervisor_module.ResearchEvidenceSupervisor._complete_atomic_capability
    )
    assert source.count("connection.commit()") == 1
    assert source.index("_atomic_publish_noreplace") < source.index(
        "connection.commit()"
    )
    assert "self.repository.connection_factory()" in source
    repository_source = inspect.getsource(
        PostgresResearchOSRepository.import_manifest
    )
    assert repository_source.index(
        "_verify_m4_v2_failed_task_recovery_import"
    ) < repository_source.index("_verify_mainline_completion_records")


def test_engineering_boundary_has_zero_runtime_or_operator_actions() -> None:
    changed = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not any(" runtime/" in line or line.endswith(" runtime") for line in changed)
    assert not any("data/output" in line for line in changed)
    for builder in (
        marginal_builder.build_manifest,
        temporal_builder.build_manifest,
        joint_builder.build_manifest,
        global_builder.build_manifest,
    ):
        source = inspect.getsource(builder)
        assert "import_manifest" not in source
        assert "run_once" not in source
        assert "promotion" not in source.lower() or "promotion_gate_opened" in source
    successor = supervisor_module.M4V2SuccessorCapability
    assert not hasattr(successor, "promote")
    assert (
        M4_P3_PREDICTIVE_PREREGISTRATION_FACT
        not in _successor_payload()["facts"]["artifacts"]
    )
