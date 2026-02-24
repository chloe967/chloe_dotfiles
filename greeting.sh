#!/bin/zsh
# Bobtail squid greeting - only for interactive shells
[[ -o interactive ]] || return 0

cat << 'SQUID'

                  ___
               .-'   '-.
              /  .   .   \
             |  (o) (o)   |
             |    ___      |
              \  '---'   /
               '-.___.-'
              /  / | \  \
             /  /  |  \  \
            {  {   |   }  }
             \  \  |  /  /
              '. '.|.' .'
                '--^--'
              ~~ ~ ~ ~ ~~
           ~~~  ~ ~ ~  ~~~
         ~~ ~~~ ~ ~ ~~~ ~~

   hello from the deep! ^_^

SQUID
